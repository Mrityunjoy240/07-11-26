import { useState, useEffect, useRef, useCallback } from 'react';
import { Message, ChatState } from '../types';
import { API_CONFIG } from '../config';

const INITIAL_MESSAGE: Message = {
    id: 'init',
    text: "Hi there! I'm your college assistant. Ask me anything about admissions, fees, courses, events, or any other college-related questions!",
    sender: 'bot',
    timestamp: new Date(),
};

const QUICK_REPLIES = [
    'Admission requirements',
    'Fee structure',
    'Available courses',
    'Campus events',
    'Contact information',
];

export function useChat() {
    const [state, setState] = useState<ChatState>({
        messages: [INITIAL_MESSAGE],
        isOpen: false,
        isLoading: false,
        error: null,
    });

    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [state.messages, scrollToBottom]);

    const toggleChat = useCallback(() => {
        setState(prev => ({ ...prev, isOpen: !prev.isOpen }));
    }, []);

    const closeChat = useCallback(() => {
        setState(prev => ({ ...prev, isOpen: false }));
    }, []);

    const addMessage = useCallback((text: string, sender: 'user' | 'bot') => {
        const newMessage: Message = {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            text,
            sender,
            timestamp: new Date(),
        };
        setState(prev => ({
            ...prev,
            messages: [...prev.messages, newMessage],
        }));
        return newMessage;
    }, []);

    const sendMessage = useCallback(async (text: string) => {
        if (!text.trim()) return;

        addMessage(text, 'user');
        setState(prev => ({ ...prev, isLoading: true, error: null }));

        // Create a placeholder message for the bot's streaming response
        const botMessageId = `${Date.now()}-bot`;
        const initialBotMessage: Message = {
            id: botMessageId,
            text: '',
            sender: 'bot',
            timestamp: new Date(),
        };

        setState(prev => ({
            ...prev,
            messages: [...prev.messages, initialBotMessage],
        }));

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/qa/query-stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: text }),
            });

            if (!response.ok) throw new Error('Failed to get response');

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let fullText = '';

            if (reader) {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const dataStr = line.slice(6).trim();
                            if (dataStr === '[DONE]') continue;

                            try {
                                const data = JSON.parse(dataStr);
                                if (data.text) {
                                    fullText += data.text;
                                    // Update the specific bot message in state
                                    setState(prev => ({
                                        ...prev,
                                        messages: prev.messages.map(msg =>
                                            msg.id === botMessageId ? { ...msg, text: fullText } : msg
                                        ),
                                    }));
                                }
                            } catch (e) {
                                console.error('Error parsing chunk:', e);
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Chat error:', error);
            setState(prev => ({
                ...prev,
                error: 'Connection error. Please try again.',
            }));
            // Update the bot message with an error
            setState(prev => ({
                ...prev,
                messages: prev.messages.map(msg =>
                    msg.id === botMessageId ? { ...msg, text: "I'm having trouble connecting. Please try again in a moment." } : msg
                ),
            }));
        } finally {
            setState(prev => ({ ...prev, isLoading: false }));
        }
    }, [addMessage]);

    const clearChat = useCallback(() => {
        setState(prev => ({
            ...prev,
            messages: [INITIAL_MESSAGE],
            error: null,
        }));
    }, []);

    return {
        ...state,
        messagesEndRef,
        toggleChat,
        closeChat,
        sendMessage,
        clearChat,
        quickReplies: QUICK_REPLIES,
    };
}
