import React, { useState, useRef, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import VoiceButton from './components/VoiceButton'

const API_URL = '/api'

export default function App() {
  const [messages, setMessages] = useState([])
  const [sessionId] = useState(() => 'session_' + Math.random().toString(36).substr(2, 9))
  const [loading, setLoading] = useState(false)

  const handleSend = async (text) => {
    if (!text.trim() || loading) return

    // Add user message
    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })
      const data = await res.json()

      // Add assistant message
      const assistantMsg = { role: 'assistant', content: data.answer, source: data.source }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      console.error('Query failed:', err)
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleVoice = async (text) => {
    if (text) {
      await handleSend(text)
    }
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>🎓 BCREC AI Assistant</h1>
        <p style={styles.subtitle}>Ask about admissions, fees, courses, or campus life</p>
      </header>

      <ChatWindow messages={messages} loading={loading} />

      <div style={styles.inputArea}>
        <input
          type="text"
          placeholder="Type your question..."
          style={styles.input}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSend(e.target.value)
              e.target.value = ''
            }
          }}
          disabled={loading}
        />
        <VoiceButton onResult={handleVoice} disabled={loading} />
      </div>
    </div>
  )
}

const styles = {
  container: {
    maxWidth: 600,
    margin: '0 auto',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#fff',
    boxShadow: '0 0 20px rgba(0,0,0,0.1)',
  },
  header: {
    padding: '20px',
    background: '#1a237e',
    color: '#fff',
    textAlign: 'center',
  },
  title: {
    fontSize: 20,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    opacity: 0.8,
  },
  inputArea: {
    display: 'flex',
    padding: 12,
    gap: 8,
    borderTop: '1px solid #eee',
    background: '#fafafa',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    fontSize: 16,
    border: '1px solid #ddd',
    borderRadius: 24,
    outline: 'none',
  },
}
