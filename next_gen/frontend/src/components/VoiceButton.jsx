import React, { useState, useRef } from 'react'

export default function VoiceButton({ onResult, disabled }) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(true)
  const recognitionRef = useRef(null)

  const startListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setSupported(false)
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()

    recognition.lang = 'en-IN'
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onstart = () => setListening(true)

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      onResult(transcript)
    }

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error)
      setListening(false)
    }

    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    recognition.start()
  }

  const stopListening = () => {
    recognitionRef.current?.stop()
    setListening(false)
  }

  if (!supported) {
    return null
  }

  return (
    <button
      onClick={listening ? stopListening : startListening}
      disabled={disabled}
      style={{
        ...styles.button,
        ...(listening ? styles.listening : {}),
        ...(disabled ? styles.disabled : {}),
      }}
      title={listening ? 'Stop listening' : 'Speak'}
    >
      {listening ? '⏹' : '🎤'}
    </button>
  )
}

const styles = {
  button: {
    width: 48,
    height: 48,
    borderRadius: '50%',
    border: 'none',
    background: '#1a237e',
    color: '#fff',
    fontSize: 20,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  listening: {
    background: '#d32f2f',
    animation: 'pulse 1s infinite',
  },
  disabled: {
    background: '#ccc',
    cursor: 'not-allowed',
  },
}
