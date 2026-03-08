import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from './axios';

export interface Project {
    id: number;
    name: string;
    description?: string;
}

interface ProjectContextType {
    projects: Project[];
    currentProject: Project | null;
    setCurrentProject: (project: Project) => void;
    refreshProjects: () => Promise<void>;
    isLoading: boolean;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
    const { projectId } = useParams<{ projectId: string }>();
    const navigate = useNavigate();

    const [projects, setProjects] = useState<Project[]>([]);
    const [currentProject, setCurrentProjectState] = useState<Project | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const fetchProjects = async () => {
        try {
            const res = await api.get('/projects');
            setProjects(res.data);

            if (res.data.length > 0) {
                // Determine active project based on URL first, fallback to storage/first available
                const targetIdStr = projectId || localStorage.getItem('currentProjectId');
                const targetId = targetIdStr ? parseInt(targetIdStr.toString()) : res.data[0].id;

                const found = res.data.find((p: Project) => p.id === targetId);

                if (found) {
                    setCurrentProjectState(found);
                    localStorage.setItem('currentProjectId', found.id.toString());

                    // If URL is missing or doesn't match the valid found project, redirect
                    if (projectId !== found.id.toString()) {
                        navigate(`/${found.id}/analysis`, { replace: true });
                    }
                } else {
                    // Invalid ID provided, fallback to first project
                    const validFallback = res.data[0];
                    setCurrentProjectState(validFallback);
                    localStorage.setItem('currentProjectId', validFallback.id.toString());
                    if (projectId !== validFallback.id.toString()) {
                        navigate(`/${validFallback.id}/analysis`, { replace: true });
                    }
                }
            } else {
                setCurrentProjectState(null);
                localStorage.removeItem('currentProjectId');
            }
        } catch (err) {
            console.error("Failed to fetch projects", err);
        } finally {
            setIsLoading(false);
        }
    };

    // Allow auth token or projectId changes to trigger a reload logic
    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            fetchProjects();
        } else {
            setIsLoading(false);
        }
    }, [projectId]);

    const setCurrentProject = (p: Project) => {
        setCurrentProjectState(p);
        localStorage.setItem('currentProjectId', p.id.toString());
    };

    return (
        <ProjectContext.Provider value={{ projects, currentProject, setCurrentProject, refreshProjects: fetchProjects, isLoading }}>
            {children}
        </ProjectContext.Provider>
    );
}

export function useProject() {
    const context = useContext(ProjectContext);
    if (context === undefined) {
        throw new Error('useProject must be used within a ProjectProvider');
    }
    return context;
}
