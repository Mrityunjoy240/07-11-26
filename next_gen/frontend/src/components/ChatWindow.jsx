import React, { useEffect, useRef } from 'react'

export default function ChatWindow({ messages, loading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  return (
    <div style={styles.container}>
      {messages.length === 0 && (
        <div style={styles.welcome}>
          <p style={styles.welcomeText}>Welcome! I can help you with:</p>
          <div style={styles.suggestions}>
            {['CSE fees', 'Placement info', 'Hostel details', 'Principal name'].map(q => (
              <button
                key={q}
                style={styles.suggestion}
                onClick={() => {
                  const event = new CustomEvent('suggest', { detail: q })
                  window.dispatchEvent(event)
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {messages.map((msg, i) => (
        <div key={i} style={{
          ...styles.bubble,
          ...(msg.role === 'user' ? styles.userBubble : styles.assistantBubble),
        }}>
          <div style={styles.message}>{msg.content}</div>
          {msg.source && (
            <div style={styles.meta}>{msg.source}</div>
          )}
        </div>
      ))}

      {loading && (
        <div style={{ ...styles.bubble, ...styles.assistantBubble }}>
          <div style={styles.typing}>
            <span style={styles.dot}>.</span>
            <span style={styles.dot}>.</span>
            <span style={styles.dot}>.</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}

const styles = {
  container: {
    flex: 1,
    overflow: 'auto',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  welcome: {
    textAlign: 'center',
    padding: '40px 20px',
    color: '#666',
  },
  welcomeText: {
    fontSize: 16,
    marginBottom: 16,
  },
  suggestions: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    justifyContent: 'center',
  },
  suggestion: {
    padding: '8px 16px',
    border: '1px solid #1a237e',
    borderRadius: 20,
    background: '#fff',
    color: '#1a237e',
    cursor: 'pointer',
    fontSize: 14,
  },
  bubble: {
    maxWidth: '80%',
    padding: '12px 16px',
    borderRadius: 16,
    lineHeight: 1.5,
  },
  userBubble: {
    alignSelf: 'flex-end',
    background: '#1a237e',
    color: '#fff',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    background: '#f0f0f0',
    color: '#333',
    borderBottomLeftRadius: 4,
  },
  message: {
    fontSize: 15,
  },
  meta: {
    fontSize: 11,
    color: '#999',
    marginTop: 4,
  },
  typing: {
    display: 'flex',
    gap: 4,
  },
  dot: {
    fontSize: 20,
    animation: 'blink 1.4s infinite both',
  },
}
