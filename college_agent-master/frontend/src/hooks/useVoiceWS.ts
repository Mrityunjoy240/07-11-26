import { useRef, useCallback, useEffect } from 'react';

interface VoiceWSMessage {
  type: 'token' | 'audio' | 'error' | 'done';
  data: any;
  format?: string;
  message?: string;
}

interface UseVoiceWSOptions {
  apiBase: string;
  onToken?: (token: string) => void;
  onAudio?: (audioUrl: string) => void;
  onError?: (error: string) => void;
  onDone?: (fullText: string) => void;
}

export function useVoiceWS(options: UseVoiceWSOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const fullAnswerRef = useRef('');
  const onTokenRef = useRef(options.onToken);
  const onAudioRef = useRef(options.onAudio);
  const onErrorRef = useRef(options.onError);
  const onDoneRef = useRef(options.onDone);
  const apiBaseRef = useRef(options.apiBase);

  useEffect(() => { onTokenRef.current = options.onToken; }, [options.onToken]);
  useEffect(() => { onAudioRef.current = options.onAudio; }, [options.onAudio]);
  useEffect(() => { onErrorRef.current = options.onError; }, [options.onError]);
  useEffect(() => { onDoneRef.current = options.onDone; }, [options.onDone]);
  useEffect(() => { apiBaseRef.current = options.apiBase; }, [options.apiBase]);

  const sendText = useCallback((text: string, language: string = 'en-IN') => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    fullAnswerRef.current = '';

    const wsUrl = apiBaseRef.current.replace(/^http/, 'ws') + '/qa/ws/voice';
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'text', data: text, language }));
    };

    ws.onmessage = (event) => {
      const msg: VoiceWSMessage = JSON.parse(event.data);

      switch (msg.type) {
        case 'token':
          fullAnswerRef.current += msg.data;
          onTokenRef.current?.(msg.data);
          break;

        case 'audio': {
          const binaryStr = atob(msg.data);
          const bytes = new Uint8Array(binaryStr.length);
          for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
          }
          const blob = new Blob([bytes], { type: 'audio/wav' });
          const url = URL.createObjectURL(blob);
          onAudioRef.current?.(url);
          break;
        }

        case 'error':
          onErrorRef.current?.(msg.data || msg.message || 'Unknown error');
          break;

        case 'done':
          onDoneRef.current?.(fullAnswerRef.current);
          break;
      }
    };

    ws.onerror = () => {
      onErrorRef.current?.('WebSocket connection error');
    };

    ws.onclose = () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, []);

  const close = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => close();
  }, [close]);

  return { sendText, close };
}
