package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"
)

type JobInput struct {
	PMID          string `json:"pmid"`
	RequestParams any    `json:"request_params"`
}

type JobOutput struct {
	PMID            string `json:"pmid"`
	ResponseContent string `json:"response_content"`
	Error           string `json:"error"`
}

var (
	apiKey     string
	baseUrl    string
	httpClient *http.Client
)

func init() {
	rand.Seed(time.Now().UnixNano())
}

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "Usage: %s <input.jsonl> <output.jsonl>\n", os.Args[0])
		os.Exit(1)
	}
	inputFile := os.Args[1]
	outputFile := os.Args[2]

	apiKey = os.Getenv("OPENAI_API_KEY")
	if apiKey == "" {
		apiKey = "bislaprom3#"
	}

	baseUrl = os.Getenv("OPENAI_BASE_URL")
	if baseUrl == "" {
		baseUrl = "http://localhost:11433/v1"
	}
	
	// Ensure we point to the chat completions endpoint
	urlStr := baseUrl
	if urlStr[len(urlStr)-1] != '/' {
		urlStr += "/"
	}
	urlStr += "chat/completions"

	concurrencyLimitStr := os.Getenv("LLM_CONCURRENCY_LIMIT")
	concurrencyLimit := 1024
	if val, err := strconv.Atoi(concurrencyLimitStr); err == nil && val > 0 {
		concurrencyLimit = val
	}

	// Setup high-throughput HTTP client
	// PERFORMANCE TUNING: Disabling HTTP/2 completely to prevent "sticky routing"
	// through the HAProxy/LiteLLM. By forcing thousands of physical HTTP/1.1 TCP 
	// connections (MaxConnsPerHost), we force the downstream proxy to balance
	// the traffic across all 8 vLLM servers instead of funneling it into 1.
	transport := &http.Transport{
		MaxIdleConns:        concurrencyLimit * 2,
		MaxIdleConnsPerHost: concurrencyLimit * 2,
		MaxConnsPerHost:     concurrencyLimit * 2,
		IdleConnTimeout:     90 * time.Second,
		ForceAttemptHTTP2:   false,
	}
	httpClient = &http.Client{
		Transport: transport,
		Timeout:   600 * time.Second,
	}

	inFile, err := os.Open(inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error opening input file: %v\n", err)
		os.Exit(1)
	}
	defer inFile.Close()

	outFile, err := os.Create(outputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating output file: %v\n", err)
		os.Exit(1)
	}
	defer outFile.Close()

	var jobs []JobInput
	scanner := bufio.NewScanner(inFile)
	buf := make([]byte, 0, 64*1024)
	scanner.Buffer(buf, 10*1024*1024) // Allow up to 10MB per line for giant contexts
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			continue
		}
		var job JobInput
		if err := json.Unmarshal(line, &job); err != nil {
			fmt.Fprintf(os.Stderr, "Error parsing job JSON: %v. Line: %s\n", err, string(line[:min(len(line), 100)]))
			continue
		}
		jobs = append(jobs, job)
	}

	totalJobs := len(jobs)
	fmt.Fprintf(os.Stderr, "Loaded %d jobs. Starting worker pool with concurrency %d...\n", totalJobs, concurrencyLimit)

	jobChan := make(chan JobInput, len(jobs))
	for _, job := range jobs {
		jobChan <- job
	}
	close(jobChan)

	var wg sync.WaitGroup
	var outMutex sync.Mutex
	completed := 0
	startTime := time.Now()

	outWriter := bufio.NewWriter(outFile)

	for i := 0; i < concurrencyLimit; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobChan {
				out := processJob(urlStr, job)
				
				outBytes, _ := json.Marshal(out)
				
				outMutex.Lock()
				outWriter.Write(outBytes)
				outWriter.WriteString("\n")
				completed++
				if completed%50 == 0 || completed == totalJobs {
					elapsed := time.Since(startTime).Seconds()
					rate := float64(completed) / elapsed
					fmt.Fprintf(os.Stderr, "[GO] Processed %d/%d (%.1f%%) - %.2f it/s\n", completed, totalJobs, float64(completed)/float64(totalJobs)*100, rate)
				}
				outMutex.Unlock()
			}
		}()
	}

	wg.Wait()
	outWriter.Flush()
	fmt.Fprintf(os.Stderr, "\n[GO] All jobs finished in %.2f seconds.\n", time.Since(startTime).Seconds())
}

type OpenAIResponse struct {
	Choices []struct {
		Message struct {
			Content string `json:"content"`
		} `json:"message"`
	} `json:"choices"`
}

func processJob(urlStr string, job JobInput) JobOutput {
	out := JobOutput{PMID: job.PMID}

	payloadBytes, err := json.Marshal(job.RequestParams)
	if err != nil {
		out.Error = fmt.Sprintf("failed to marshal request params: %v", err)
		return out
	}

	var lastErr string
	for attempt := 0; attempt < 30; attempt++ {
		if attempt > 0 {
			shift := attempt
			if shift > 7 {
				shift = 7
			}
			backoff := (0.5 + rand.Float64()*1.5) * float64(uint(1)<<shift)
			time.Sleep(time.Duration(backoff * float64(time.Second)))
		}

		req, err := http.NewRequest("POST", urlStr, bytes.NewReader(payloadBytes))
		if err != nil {
			lastErr = err.Error()
			continue
		}

		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+apiKey)
		req.Close = false

		resp, err := httpClient.Do(req)
		if err != nil {
			lastErr = err.Error()
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()

		if resp.StatusCode != 200 {
			lastErr = fmt.Sprintf("HTTP %d: %s", resp.StatusCode, string(body))
			continue
		}

		var oaiResp OpenAIResponse
		if err := json.Unmarshal(body, &oaiResp); err != nil {
			lastErr = fmt.Sprintf("failed to parse JSON response: %v", err)
			continue
		}

		if len(oaiResp.Choices) > 0 {
			out.ResponseContent = oaiResp.Choices[0].Message.Content
			return out
		} else {
			lastErr = "missing choices in response"
		}
	}

	out.Error = lastErr
	fmt.Fprintf(os.Stderr, "     └─ [Go Retry] All 30 attempts failed for PMID %s: %s\n", job.PMID, lastErr)
	return out
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
