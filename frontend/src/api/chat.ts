export async function sendChatMessage(message: string) {
  return fetch('/api/chat_with_memory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });
}
