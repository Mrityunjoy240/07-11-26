import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Box,
    Button,
    Paper,
    Typography,
    IconButton,
    CircularProgress,
    Chip,
    Alert,
    TextField
} from '@mui/material';
import {
    Mic,
    MicOff,
    VolumeUp,
    Send,
    Chat as ChatIcon,
    Add as AddIcon
} from '@mui/icons-material';
import { useVoice } from '../../hooks/useVoice';
import { useVoiceWS } from '../../hooks/useVoiceWS';
import { useNoiseCancellation } from '../../hooks/useNoiseCancellation';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface VoiceChatProps {
    conversationId: string | null;
    onConversationChange?: (id: string | null) => void;
    onNewChat?: () => void;
}

const VoiceChat: React.FC<VoiceChatProps> = ({
    conversationId,
    onConversationChange,
    onNewChat,
}) => {
    // Dynamically resolve API base: use current domain in production, localhost in development
    const API_BASE = import.meta.env.VITE_API_URL || window.location.origin;
    const QUERY_ENDPOINT = '/qa/query'; // PRODUCTION: Using Consolidated Query
    const [messages, setMessages] = useState<Message[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [textInput, setTextInput] = useState('');
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [health, setHealth] = useState<{ status: string; ollama_connected: boolean; groq_available: boolean } | null>(null);
    const [sessionId] = useState<string | null>(null);
    const [sarvamError, setSarvamError] = useState<string | null>(null);
    const [continuousMode, setContinuousMode] = useState(false);
    const [pipelineMode, setPipelineMode] = useState(false);
    const [streamingAnswer, setStreamingAnswer] = useState('');

    const audioQueueRef = useRef<string[]>([]);
    const isPlayingRef = useRef(false);
    const continuousModeRef = useRef(false);
    
    // Keep ref in sync for callbacks
    useEffect(() => {
        continuousModeRef.current = continuousMode;
    }, [continuousMode]);

    const playNextInQueue = useCallback(async (autoRestartMic: boolean = false) => {
        if (audioQueueRef.current.length === 0) {
            isPlayingRef.current = false;
            setIsSpeaking(false);
            
            // If continuous mode is enabled, restart the microphone after the AI finishes speaking
            if (autoRestartMic && continuousModeRef.current) {
                setTimeout(() => {
                    startRecording();
                }, 500);
            }
            return;
        }

        isPlayingRef.current = true;
        setIsSpeaking(true);
        const nextUrl = audioQueueRef.current.shift();

        if (nextUrl) {
            const audio = new Audio(nextUrl);
            audio.onended = () => playNextInQueue(true); // Pass true to trigger auto-restart on complete
            audio.onerror = () => playNextInQueue(true);
            try {
                await audio.play();
            } catch (err) {
                console.error("Autoplay failed:", err);
                playNextInQueue(true);
            }
        }
    }, []);

    const addToAudioQueue = useCallback((url: string) => {
        audioQueueRef.current.push(url);
        if (!isPlayingRef.current) {
            playNextInQueue();
        }
    }, [playNextInQueue]);

    const speakAnswer = useCallback(async (text: string, lang: string = 'en-IN') => {
        if (!text.trim()) return;

        try {
            audioQueueRef.current = [];
            setIsSpeaking(true);

            // Using faster direct endpoint that bypasses disk
            const res = await fetch(`${API_BASE}/qa/tts-direct`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    language: lang,
                    session_id: sessionId || "default"
                }),
            });

            if (res.ok) {
                const blob = await res.blob();
                const audioUrl = URL.createObjectURL(blob);
                addToAudioQueue(audioUrl);
            } else {
                console.error("TTS generation failed");
                setIsSpeaking(false);
            }
        } catch (error) {
            console.error('Error in speakAnswer:', error);
            setIsSpeaking(false);
        }
    }, [sessionId, API_BASE, addToAudioQueue]);

    const { sendText: sendPipelineText } = useVoiceWS({
        apiBase: API_BASE,
        onToken: (token) => {
            setStreamingAnswer(prev => prev + token);
        },
        onAudio: (url) => {
            addToAudioQueue(url);
        },
        onError: (error) => {
            console.error('Pipeline error:', error);
            setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error}` }]);
            setIsProcessing(false);
            setStreamingAnswer('');
        },
        onDone: (fullText) => {
            setMessages(prev => [...prev, { role: 'assistant', content: fullText }]);
            setStreamingAnswer('');
            setIsProcessing(false);
        }
    });

    const handlePipelineQuery = useCallback(async (queryText?: string, lang: string = 'en-IN') => {
        const textToSend = queryText || textInput;
        if (!textToSend.trim() || isProcessing) return;

        setIsProcessing(true);
        setIsSpeaking(false);
        audioQueueRef.current = [];

        const userMessage: Message = { role: 'user', content: textToSend };
        setMessages(prev => [...prev, userMessage]);

        if (!queryText) setTextInput('');

        setStreamingAnswer('');
        sendPipelineText(textToSend, lang);
    }, [textInput, isProcessing, sendPipelineText]);

    // Function to submit query
    const handleQuery = useCallback(async (queryText?: string, lang: string = 'en-IN') => {
        if (pipelineMode) {
            return handlePipelineQuery(queryText, lang);
        }

        const textToSend = queryText || textInput;
        if (!textToSend.trim() || isProcessing) return;

        setIsProcessing(true);
        setIsSpeaking(false);
        audioQueueRef.current = [];

        const userMessage: Message = { role: 'user', content: textToSend };
        setMessages(prev => [...prev, userMessage]);

        if (!queryText) setTextInput('');

        try {
            const res = await fetch(`${API_BASE}${QUERY_ENDPOINT}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    message: textToSend,
                    conversation_id: conversationId
                }),
            });

            if (res.ok) {
                const data = await res.json();
                const answer = data.answer;

                const assistantMessage: Message = { role: 'assistant', content: answer };
                setMessages(prev => [...prev, assistantMessage]);

                if (data.conversation_id && data.conversation_id !== conversationId) {
                    onConversationChange?.(data.conversation_id);
                }

                if (queryText) {
                    speakAnswer(answer, lang);
                }
            } else {
                const errorMsg = 'Error: Could not process your request. Please try again.';
                setMessages(prev => [...prev, { role: 'assistant', content: errorMsg }]);
            }
        } catch (error) {
            console.error('Error processing query:', error);
            setMessages(prev => [...prev, { role: 'assistant', content: 'Error: Could not process your request. Please try again.' }]);
        } finally {
            setIsProcessing(false);
        }
    }, [textInput, isProcessing, API_BASE, QUERY_ENDPOINT, conversationId, onConversationChange, speakAnswer, pipelineMode, handlePipelineQuery]);

    // Initialize voice hook with callback for auto-answer
    const voice = useVoice({ 
        language: 'auto', 
        apiBase: API_BASE,
        onTranscriptionComplete: (result) => {
            console.log("Transcription complete callback:", result);
            handleQuery(result.text, result.language);
        }
    });

    const noiseCanceller = useNoiseCancellation({
        enabled: false,
        noiseGateThreshold: -50,
        highPassFrequency: 100,
        noiseReduction: 0.3
    });

    const stopSpeaking = useCallback(() => {
        setIsSpeaking(false);
    }, []);

    useEffect(() => {
        if (!isSpeaking) return;
        if (voice.isRecording && (voice.transcript || voice.interimTranscript)) {
            console.log('Barge-in detected! Stopping playback.');
            stopSpeaking();
        }
    }, [voice.transcript, voice.interimTranscript, isSpeaking, voice.isRecording, stopSpeaking]);

    useEffect(() => {
        return () => {
            noiseCanceller.cleanup();
        };
    }, [noiseCanceller]);

    // Load conversation messages when conversationId changes
    useEffect(() => {
        if (conversationId) {
            loadConversationMessages(conversationId);
        } else {
            setMessages([]);
        }
    }, [conversationId]);

    // Load health status
    useEffect(() => {
        const loadHealth = async () => {
            try {
                const res = await fetch(`${API_BASE}/qa/health`);
                if (res.ok) {
                    const data = await res.json();
                    setHealth(data);
                }
            } catch (e) {
                setHealth(null);
            }
        };
        loadHealth();
    }, [API_BASE]);

    const loadConversationMessages = async (convId: string) => {
        try {
            const res = await fetch(`${API_BASE}/api/conversations/${convId}`);
            if (res.ok) {
                const data = await res.json();
                const loadedMessages: Message[] = data.messages.map((m: { role: string; content: string }) => ({
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                }));
                setMessages(loadedMessages);
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    };

    // Audio Context priming to bypass browser autoplay restrictions
    const unlockAudio = useCallback(() => {
        const context = new (window.AudioContext || (window as any).webkitAudioContext)();
        if (context.state === 'suspended') {
            context.resume();
        }
        // Play a tiny silent buffer to "prime" the system
        const buffer = context.createBuffer(1, 1, 22050);
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.start(0);
    }, []);

    const playBeep = useCallback(() => {
        try {
            const context = new (window.AudioContext || (window as any).webkitAudioContext)();
            const oscillator = context.createOscillator();
            const gainNode = context.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(context.destination);
            
            oscillator.type = 'sine';
            // A soft, polite 600Hz tone like a walkie-talkie cue
            oscillator.frequency.setValueAtTime(600, context.currentTime); 
            
            // Low volume that fades out quickly
            gainNode.gain.setValueAtTime(0.1, context.currentTime); 
            gainNode.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.15); 
            
            oscillator.start(context.currentTime);
            oscillator.stop(context.currentTime + 0.15);
        } catch (e) {
            console.error("Could not play beep", e);
        }
    }, []);

    const startRecording = async () => {
        if (isProcessing) return;

        try {
            // Unlock audio system on the first user gesture (click)
            unlockAudio();
            playBeep(); // <--- Play the auditory cue
            await voice.startRecording();
        } catch (error) {
            console.error('Error starting recording:', error);
        }
    };
    
    useEffect(() => {
        setSarvamError(voice.error);
    }, [voice.error]);

    const stopRecording = async () => {
        // Voice Activity Detection handles the automatic stopping
        // But users can still click the button to stop manually
        await voice.stopRecording();
    };

    const handleNewChat = () => {
        setMessages([]);
        onNewChat?.();
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 160px)' }}>
            {/* Header */}
            <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                p: 2,
                borderBottom: '1px solid #e0e0e0'
            }}>
                <Typography variant="h5" sx={{ fontWeight: 600 }}>
                    BCREC Voice Assistant
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                        label={health?.groq_available ? "Groq Active" : "Groq Not Configured"}
                        color={health?.groq_available ? "info" : "warning"}
                        size="small"
                        sx={{ fontSize: '0.7rem' }}
                    />
                    <Chip
                        label="Sarvam STT/TTS"
                        color={voice.error ? "error" : "success"}
                        size="small"
                        sx={{ fontSize: '0.7rem' }}
                    />
                    <Button
                        variant={continuousMode ? "contained" : "outlined"}
                        color={continuousMode ? "success" : "primary"}
                        size="small"
                        onClick={() => setContinuousMode(!continuousMode)}
                        sx={{ ml: 1, fontSize: '0.75rem', borderRadius: 2 }}
                    >
                        {continuousMode ? "Hands-Free: ON" : "Hands-Free: OFF"}
                    </Button>
                    <Button
                        variant={pipelineMode ? "contained" : "outlined"}
                        color={pipelineMode ? "secondary" : "primary"}
                        size="small"
                        onClick={() => setPipelineMode(!pipelineMode)}
                        sx={{ ml: 1, fontSize: '0.75rem', borderRadius: 2 }}
                    >
                        {pipelineMode ? "Stream: ON" : "Stream: OFF"}
                    </Button>
                    <Button
                        variant="outlined"
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={handleNewChat}
                    >
                        New Chat
                    </Button>
                </Box>
            </Box>

            {/* Messages Area */}
            <Box sx={{ 
                flexGrow: 1, 
                overflow: 'auto', 
                p: 3,
                display: 'flex',
                flexDirection: 'column',
                gap: 2
            }}>
                {messages.length === 0 && !isProcessing && (
                    <Box sx={{ 
                        flexGrow: 1, 
                        display: 'flex', 
                        flexDirection: 'column',
                        alignItems: 'center', 
                        justifyContent: 'center',
                        textAlign: 'center',
                        color: '#666'
                    }}>
                        <ChatIcon sx={{ fontSize: 64, mb: 2, opacity: 0.3 }} />
                        <Typography variant="h6" gutterBottom>
                            Welcome to BCREC Voice Assistant
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Ask me about admissions, fees, placements, hostel, courses, and more!
                        </Typography>
                    </Box>
                )}

                {messages.map((msg, index) => (
                    <Box
                        key={index}
                        sx={{
                            display: 'flex',
                            justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                        }}
                    >
                        <Paper
                            elevation={1}
                            sx={{
                                p: 2,
                                maxWidth: '80%',
                                bgcolor: msg.role === 'user' ? '#1a237e' : '#f5f5f5',
                                color: msg.role === 'user' ? 'white' : 'text.primary',
                                borderRadius: 2,
                            }}
                        >
                            <Typography variant="body1">
                                {msg.content}
                            </Typography>
                            {msg.role === 'assistant' && (
                                <Box sx={{ mt: 1, textAlign: 'right' }}>
                                    <IconButton
                                        size="small"
                                        onClick={() => speakAnswer(msg.content)}
                                        disabled={isSpeaking}
                                        sx={{ color: '#666' }}
                                    >
                                        <VolumeUp fontSize="small" />
                                    </IconButton>
                                </Box>
                            )}
                        </Paper>
                    </Box>
                ))}

                {isProcessing && !streamingAnswer && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                        <Paper sx={{ p: 2, bgcolor: '#f5f5f5', borderRadius: 2 }}>
                            <CircularProgress size={20} />
                            <Typography variant="body2" sx={{ ml: 2, display: 'inline' }}>
                                Processing...
                            </Typography>
                        </Paper>
                    </Box>
                )}

                {streamingAnswer && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-start' }}>
                        <Paper sx={{ p: 2, bgcolor: '#e8f5e9', borderRadius: 2, maxWidth: '80%' }}>
                            <Typography variant="body1">
                                {streamingAnswer}
                                {isProcessing && ' ...'}
                            </Typography>
                        </Paper>
                    </Box>
                )}
            </Box>

            {/* Input Area */}
            <Box sx={{ 
                p: 2, 
                borderTop: '1px solid #e0e0e0',
                bgcolor: 'white'
            }}>
                {/* Voice Support Warning */}
                {!voice.isSupported && (
                    <Alert severity="warning" sx={{ mb: 2 }}>
                        Voice recognition not supported. Please use Chrome, Edge, or Safari.
                    </Alert>
                )}
                
                {/* Sarvam Error */}
                {sarvamError && (
                    <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSarvamError(null)}>
                        {sarvamError}
                    </Alert>
                )}

                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                    {/* Mic Button */}
                    <IconButton
                        onClick={voice.isRecording ? stopRecording : startRecording}
                        disabled={!voice.isSupported || isProcessing}
                        sx={{
                            bgcolor: voice.isRecording ? '#d32f2f' : '#1a237e',
                            color: 'white',
                            '&:hover': { bgcolor: voice.isRecording ? '#b71c1c' : '#0d47a1' },
                            width: 56,
                            height: 56,
                        }}
                    >
                        {voice.isRecording ? <MicOff /> : <Mic />}
                    </IconButton>

                    {/* Text Input */}
                    <TextField
                        fullWidth
                        placeholder="Type your question..."
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
                        variant="outlined"
                        disabled={isProcessing}
                        sx={{
                            '& .MuiOutlinedInput-root': { 
                                borderRadius: 3,
                                bgcolor: '#f9fafb'
                            }
                        }}
                    />

                    {/* Send Button */}
                    <Button
                        variant="contained"
                        onClick={() => handleQuery()}
                        disabled={!textInput.trim() || isProcessing}
                        sx={{ 
                            borderRadius: 3, 
                            px: 3,
                            minWidth: 100,
                            height: 56
                        }}
                    >
                        Send <Send sx={{ ml: 1 }} />
                    </Button>
                </Box>

                {/* Live Transcript */}
                {(voice.transcript || voice.interimTranscript) && (
                    <Box sx={{ mt: 2, p: 2, bgcolor: '#fff3e0', borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">
                            {voice.isRecording ? "Listening:" : "Transcribed:"} 
                        </Typography>
                        <Typography variant="body2">
                            {voice.transcript}
                            <span style={{ color: '#999' }}>{voice.interimTranscript}</span>
                        </Typography>
                    </Box>
                )}
            </Box>
        </Box>
    );
};

export default VoiceChat;
