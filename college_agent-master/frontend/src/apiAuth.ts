export const API_TOKEN: string = import.meta.env.VITE_API_TOKEN || '';

export function authHeaders(): Record<string, string> {
    return API_TOKEN ? { 'X-API-Key': API_TOKEN } : {};
}
