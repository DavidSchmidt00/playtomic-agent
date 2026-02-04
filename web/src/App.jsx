import React from 'react'
import Chat from './components/Chat'

export default function App() {
  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Playtomic Agent</h1>
      </header>
      <main>
        <Chat />
      </main>
    </div>
  )
}
