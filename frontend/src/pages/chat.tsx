
import "../chat.css";
import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { getWebSocketUrl } from "../api"
import { API_BASE_URL } from "../api"
// ==================================================

// Types

// ==================================================

type MessageStatus = "sent" | "received" | "read";

type Conversation = {

  conversation_id: number;

  username: string;

};

type TemporaryChat = {

  username: string;

};

type ChatItem = Conversation | TemporaryChat;

type Message = {

  message_id: number;

  conversation_id: number;

  sender: string;

  recipient: string;

  content: string;

  created_at?: string;

  status?: MessageStatus;

};

type Presence = {
  status: "online" | "offline";
  last_seen?: string;
};

const statusRank: Record<MessageStatus, number> = {

  sent: 1,

  received: 2,

  read: 3,

};

function advanceStatus(

  current: MessageStatus | undefined,

  incoming: MessageStatus

): MessageStatus {

  if (!current) return incoming;

  return statusRank[incoming] > statusRank[current]

    ? incoming

    : current;

}

type ChatProps = {
  onLogout: () => void
}

// ==================================================

// Component

// ==================================================

function Chat({ onLogout }: ChatProps) {

  const token = localStorage.getItem("access_token");

  const [currentUsername, setCurrentUsername] = useState("");

  const [conversations, setConversations] = useState<Conversation[]>([]);

  const [temporaryChats, setTemporaryChats] = useState<TemporaryChat[]>([]);

  const [selectedChat, setSelectedChat] = useState<ChatItem | null>(null);

  const [messages, setMessages] = useState<Record<number, Message[]>>({});

  const [presence, setPresence] = useState<Record<string, Presence>>({});

  const [message, setMessage] = useState("");

  const [newUsername, setNewUsername] = useState("");

  const [showNewChat, setShowNewChat] = useState(false);

  const websocket = useRef<WebSocket | null>(null);

  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  const lastDeliveredAckRef = useRef<Record<number, number>>({});

  const lastReadAckRef = useRef<Record<number, number>>({});

  const currentUsernameRef = useRef("");

  const explicitlyOpenedConversationRef = useRef<number | null>(null);

  useEffect(() => {

    currentUsernameRef.current = currentUsername;

  }, [currentUsername]);

  const formatLastSeen = (lastSeen?: string): string => {

    if (!lastSeen) return "Offline";

    const date = new Date(lastSeen);

    if (Number.isNaN(date.getTime())) return "Offline";

    return `Last seen ${date.toLocaleString()}`;

  };

  const sendSocketEvent = useCallback((payload: object): void => {

    const ws = websocket.current;

    if (ws?.readyState === WebSocket.OPEN) {

      ws.send(JSON.stringify(payload));

    }

  }, []);

  // ==================================================

  // Explicit conversation selection

  // ==================================================

  const openConversation = (conversation: Conversation): void => {

    explicitlyOpenedConversationRef.current =

      conversation.conversation_id;

    setSelectedChat(conversation);

  };

  const openTemporaryChat = (chat: TemporaryChat): void => {

    // A temporary chat has no conversation ID yet.

    explicitlyOpenedConversationRef.current = null;

    setSelectedChat(chat);

  };

  // ==================================================

  // Update outgoing statuses cumulatively

  // ==================================================

  const updateOutgoingStatuses = useCallback(

    (

      conversationId: number,

      throughMessageId: number,

      incomingStatus: MessageStatus

    ): void => {

      setMessages((previous) => {

        const conversationMessages = previous[conversationId] ?? [];

        let changed = false;

        const updatedMessages = conversationMessages.map((msg) => {

          if (

            msg.sender !== currentUsernameRef.current ||

            msg.message_id > throughMessageId

          ) {

            return msg;

          }

          const nextStatus = advanceStatus(msg.status, incomingStatus);

          if (nextStatus === msg.status) return msg;

          changed = true;

          return { ...msg, status: nextStatus };

        });

        if (!changed) return previous;

        return {

          ...previous,

          [conversationId]: updatedMessages,

        };

      });

    },

    []

  );

  // ==================================================

  // Load current user

  // ==================================================

  useEffect(() => {

    if (!token) return;

    let cancelled = false;

    async function loadCurrentUser(): Promise<void> {

      try {

        const response = await fetch(`${API_BASE_URL}/me`, {

          headers: { Authorization: `Bearer ${token}` },

        });

        if (!response.ok) {

          throw new Error("Failed to get current user");

        }

        const data: { username: string } = await response.json();

        if (!cancelled) setCurrentUsername(data.username);

      } catch (error) {

        console.error("Failed to load current user:", error);

      }

    }

    void loadCurrentUser();

    return () => {

      cancelled = true;

    };

  }, [token]);

  // ==================================================

  // Load conversations

  // ==================================================

  useEffect(() => {

    if (!token) return;

    let cancelled = false;

    async function loadConversations(): Promise<void> {

      try {

        const response = await fetch(

          `${API_BASE_URL}/conversations`,

          { headers: { Authorization: `Bearer ${token}` } }

        );

        if (!response.ok) {

          throw new Error("Failed to load conversations");

        }

        const data: Conversation[] = await response.json();

        if (!cancelled) setConversations(data);

      } catch (error) {

        console.error("Failed to load conversations:", error);

      }

    }

    void loadConversations();

    return () => {

      cancelled = true;

    };

  }, [token]);

  // ==================================================

  // WebSocket connection

  // ==================================================

  useEffect(() => {

    if (!token || !currentUsername) return;

    let shouldReconnect = true;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 1000;

    const connect = (): void => {

      const ws = new WebSocket(
        getWebSocketUrl(token)
      );
      websocket.current = ws;

    ws.onopen = () => {
      console.log("WebSocket connected");
      retryDelay = 1000;
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      let parsed: unknown;

      try {
        parsed = JSON.parse(event.data);
      } catch {
        console.error("Invalid WebSocket JSON");
        return;
      }

      if (
        typeof parsed !== "object" ||
        parsed === null ||
        Array.isArray(parsed)
      ) {
        console.error("Invalid WebSocket message format");
        return;
      }

      const data = parsed as Record<string, unknown>;

      // Presence event
      if (data.type === "presence") {
        const username = data.username;
        const status = data.status;

        if (
          typeof username !== "string" ||
          (status !== "online" && status !== "offline")
        ) {
          return;
        }

        const presence: Presence = {
          status,
          last_seen:
            typeof data.last_seen === "string"
              ? data.last_seen
              : undefined,
        };

        setPresence((previous) => ({
          ...previous,
          [username]: presence,
        }));

        return;
      }

      // Message status event
      if (data.type === "message_status") {
        const conversationId = Number(data.conversation_id);
        const messageId = Number(data.message_id);
        const status = data.status;

        if (
          !Number.isInteger(conversationId) ||
          !Number.isInteger(messageId) ||
          messageId <= 0
        ) {
          return;
        }

        if (status === "received" || status === "read") {
          updateOutgoingStatuses(conversationId, messageId, status);
        }

        return;
      }

      // Normal chat message

      if (

        typeof data.message_id !== "number" ||

        typeof data.conversation_id !== "number" ||

        typeof data.sender !== "string" ||

        typeof data.recipient !== "string" ||

        typeof data.content !== "string"

      ) {

        return;

      }

      const incomingMessage: Message = {

        message_id: data.message_id,

        conversation_id: data.conversation_id,

        sender: data.sender,

        recipient: data.recipient,

        content: data.content,

        created_at:
          typeof data.created_at === "string"
            ? data.created_at
            : undefined,

        status: data.sender === currentUsername ? "sent" : undefined,

      };

      const otherUsername =

        incomingMessage.sender === currentUsername

          ? incomingMessage.recipient

          : incomingMessage.sender;

      setConversations((previous) => {

        const exists = previous.some(

          (conversation) =>

            conversation.conversation_id ===

            incomingMessage.conversation_id

        );

        if (exists) return previous;

        return [

          ...previous,

          {

            conversation_id: incomingMessage.conversation_id,

            username: otherUsername,

          },

        ];

      });

      setTemporaryChats((previous) =>

        previous.filter(

          (chat) =>

            chat.username.toLowerCase() !== otherUsername.toLowerCase()

        )

      );

      setMessages((previous) => {

        const existingMessages =

          previous[incomingMessage.conversation_id] ?? [];

        const existingIndex = existingMessages.findIndex(

          (msg) => msg.message_id === incomingMessage.message_id

        );

        if (existingIndex !== -1) {

          const updated = [...existingMessages];

          const oldMessage = updated[existingIndex];

          updated[existingIndex] = {

            ...oldMessage,

            ...incomingMessage,

            status:

              oldMessage.sender === currentUsername

                ? advanceStatus(

                    oldMessage.status,

                    incomingMessage.status ?? "sent"

                  )

                : oldMessage.status,

          };

          return {

            ...previous,

            [incomingMessage.conversation_id]: updated,

          };

        }

        const updatedMessages = [

          ...existingMessages,

          incomingMessage,

        ].sort((a, b) => a.message_id - b.message_id);

        return {

          ...previous,

          [incomingMessage.conversation_id]: updatedMessages,

        };

      });

      // Convert temporary chat to a real conversation.

      // This does NOT mark it as explicitly opened.

      setSelectedChat((previous) => {

        if (

          !previous ||

          "conversation_id" in previous ||

          previous.username.toLowerCase() !== otherUsername.toLowerCase()

        ) {

          return previous;

        }

        return {

          conversation_id: incomingMessage.conversation_id,

          username: otherUsername,

        };

      });

      // Delivery acknowledgement is independent of read status.

      if (incomingMessage.sender !== currentUsername) {

        const conversationId = incomingMessage.conversation_id;

        const messageId = incomingMessage.message_id;

        const lastAck = lastDeliveredAckRef.current[conversationId] ?? 0;

        if (messageId > lastAck) {

          lastDeliveredAckRef.current[conversationId] = messageId;

          sendSocketEvent({

            type: "message_received",

            message_id: messageId,

            conversation_id: conversationId,

          });

        }

      }

    };

    ws.onerror = (error) => {

      console.error("WebSocket error:", error);

    };

    
    ws.onclose = () => {
      console.log("WebSocket disconnected");

      if (!shouldReconnect) return;

      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, retryDelay);

      // Back off after repeated failures, up to 10 seconds.
      retryDelay = Math.min(retryDelay * 2, 10000);
    };
    }; // Close connect function

    connect();

    return () => {
      shouldReconnect = false;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);

      const activeSocket = websocket.current;
      if (activeSocket) activeSocket.close();
      websocket.current = null;
    };
  }, [
    token,
    currentUsername,
    sendSocketEvent,
    updateOutgoingStatuses,
  ]);


  // ==================================================

  // Fetch selected user's presence

  // ==================================================

 useEffect(() => {
  const username = selectedChat?.username;

  if (!token || !username) return;

  const presenceUsername: string = username;
  let cancelled = false;

  async function fetchPresence(): Promise<void> {
    try {
      const response = await fetch(
        `${API_BASE_URL}/users/${encodeURIComponent(presenceUsername)}/presence`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      // Keep the rest of your existing fetchPresence logic here.

        if (!response.ok) {

          throw new Error("Failed to fetch user presence");

        }

        const data: {

          username: string;

          status: "online" | "offline";

          last_seen?: string | null;

        } = await response.json();

        if (cancelled) return;

        setPresence((previous) => ({

          ...previous,

          [data.username]: {

            status: data.status,

            last_seen: data.last_seen ?? undefined,

          },

        }));

      } catch (error) {

        if (!cancelled) {

          console.error("Failed to fetch presence:", error);

        }

      }

    }

    void fetchPresence();

    return () => {

      cancelled = true;

    };

  }, [selectedChat?.username, token]);

  // ==================================================

  // Load conversation history

  // ==================================================

  const historyRequestedRef = useRef<Record<number, boolean>>({});

  const selectedConversationId =

    selectedChat && "conversation_id" in selectedChat

      ? selectedChat.conversation_id

      : null;

  useEffect(() => {

    if (!token || selectedConversationId === null) return;

    const conversationId = selectedConversationId;

    if (

      messages[conversationId] !== undefined ||

      historyRequestedRef.current[conversationId]

    ) {

      return;

    }

    let cancelled = false;

    historyRequestedRef.current[conversationId] = true;

    async function loadMessages(): Promise<void> {

      try {

        const response = await fetch(

          `${API_BASE_URL}/conversations/${conversationId}/messages`,

          { headers: { Authorization: `Bearer ${token}` } }

        );

        if (!response.ok) {

          throw new Error("Failed to load messages");

        }

        const data: Message[] = await response.json();

        if (cancelled) return;

        setMessages((previous) => {

          const current = previous[conversationId] ?? [];

          const currentById = new Map<number, Message>(

            current.map((msg) => [msg.message_id, msg])

          );

          const merged: Message[] = data.map((msg) => {

            const existing = currentById.get(msg.message_id);

            if (!existing) {

              return {

                ...msg,

                status:

                  msg.sender === currentUsername ? "sent" : undefined,

              };

            }

            let mergedStatus = existing.status;

            if (existing.sender === currentUsername) {

              mergedStatus = advanceStatus(

                existing.status,

                msg.status ?? "sent"

              );

            }

            return { ...msg, status: mergedStatus };

          });

          const historyIds = new Set(

            merged.map((msg) => msg.message_id)

          );

          for (const msg of current) {

            if (!historyIds.has(msg.message_id)) merged.push(msg);

          }

          merged.sort((a, b) => a.message_id - b.message_id);

          return {

            ...previous,

            [conversationId]: merged,

          };

        });

      } catch (error) {

        historyRequestedRef.current[conversationId] = false;

        if (!cancelled) {

          console.error("Failed to load messages:", error);

        }

      }

    }

    void loadMessages();

    return () => {

      cancelled = true;

    };

  }, [selectedConversationId, token, currentUsername, messages]);

  // ==================================================

  // Selected messages

  // ==================================================

  const selectedMessages: Message[] = useMemo(
  () =>
    selectedConversationId !== null
      ? messages[selectedConversationId] ?? []
      : [],
  [selectedConversationId, messages]
);

  // ==================================================

  // Acknowledge read ONLY for an explicitly opened chat

  // ==================================================

  useEffect(() => {

    if (

      selectedConversationId === null ||

      !currentUsername ||

      explicitlyOpenedConversationRef.current !== selectedConversationId

    ) {

      return;

    }

    const latestIncoming = selectedMessages.reduce<Message | null>(

      (latest, msg) => {

        if (msg.sender === currentUsername) return latest;

        if (!latest || msg.message_id > latest.message_id) {

          return msg;

        }

        return latest;

      },

      null

    );

    if (!latestIncoming) return;

    const conversationId = selectedConversationId;

    const messageId = latestIncoming.message_id;

    const lastAck = lastReadAckRef.current[conversationId] ?? 0;

    if (messageId <= lastAck) return;

    const ws = websocket.current;

    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(

      JSON.stringify({

        type: "message_read",

        message_id: messageId,

        conversation_id: conversationId,

      })

    );

    lastReadAckRef.current[conversationId] = messageId;

  }, [selectedConversationId, selectedMessages, currentUsername]);

  // ==================================================

  // Scroll to latest message

  // ==================================================

  useEffect(() => {

    const container = chatContainerRef.current;

    if (container) {

      container.scrollTop = container.scrollHeight;

    }

  }, [selectedConversationId, selectedMessages.length]);

  // ==================================================

  // Start new chat

  // ==================================================

  const startNewChat = async (): Promise<void> => {

    const username = newUsername.trim();

    if (!username || !token) return;

    try {

      const response = await fetch(

        `${API_BASE_URL}/users/${encodeURIComponent(username)}`,

        { headers: { Authorization: `Bearer ${token}` } }

      );

      if (!response.ok) {

        alert("User not found");

        return;

      }

      const user: { username: string } = await response.json();

      const existingConversation = conversations.find(

        (conversation) =>

          conversation.username.toLowerCase() ===

          user.username.toLowerCase()

      );

      if (existingConversation) {

        openConversation(existingConversation);

      } else {

        const existingTemporaryChat = temporaryChats.find(

          (chat) =>

            chat.username.toLowerCase() === user.username.toLowerCase()

        );

        if (existingTemporaryChat) {

          openTemporaryChat(existingTemporaryChat);

        } else {

          const temporaryChat: TemporaryChat = {

            username: user.username,

          };

          setTemporaryChats((previous) => [...previous, temporaryChat]);

          openTemporaryChat(temporaryChat);

        }

      }

      setNewUsername("");

      setShowNewChat(false);

    } catch (error) {

      console.error("Failed to start new chat:", error);

    }

  };

  // ==================================================

  // Send message

  // ==================================================

  const sendMessage = (): void => {

    const content = message.trim();

    const ws = websocket.current;

    if (!content || !selectedChat) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {

      alert("Not connected. Please wait for the connection.");

      return;

    }

    ws.send(

      JSON.stringify({

        recipient: selectedChat.username,

        content,

      })

    );

    setMessage("");

  };

  // ==================================================

  // Status indicator

  // ==================================================

  const renderMessageStatus = (

    status: MessageStatus | undefined

  ): React.ReactNode => {

    if (status === "read") {

      return (

        <span

          title="Read"

          aria-label="Read"

          style={{

            color: "#2563eb",

            fontSize: "14px",

            fontWeight: 700,

          }}

        >

          ✓✓

        </span>

      );

    }

    if (status === "received") {

      return (

        <span

          title="Received"

          aria-label="Received"

          style={{ color: "#6b7280", fontSize: "14px" }}

        >

          ✓✓

        </span>

      );

    }

    return (

      <span

        title="Sent"

        aria-label="Sent"

        style={{ color: "#6b7280", fontSize: "14px" }}

      >

        ✓

      </span>

    );

  };

  const selectedPresence = selectedChat

    ? presence[selectedChat.username]

    : undefined;

  // ==================================================

  // UI

  // ==================================================

  return (

    <div className="chat-layout">


     <aside className="chat-sidebar">

        <h2>Conversations</h2>

        {conversations.map((conversation) => {

          const isSelected =

            selectedConversationId === conversation.conversation_id;

          return (

            <div
              key={`conversation-${conversation.conversation_id}`}
              onClick={() => openConversation(conversation)}
              className={`conversation-item ${
                isSelected ? "selected" : ""
              }`}
            >

              {conversation.username}

            </div>

          );

        })}
        <h3>
          <button className="chat-button" onClick={onLogout}>
            Logout
          </button>
        </h3>

        {temporaryChats.map((chat) => {

          const isSelected =

            selectedConversationId === null &&

            selectedChat?.username === chat.username;

          return (

            <div
              key={`temporary-${chat.username}`}
              onClick={() => openTemporaryChat(chat)}
              className={`conversation-item ${
                isSelected ? "selected" : ""
              }`}
            >

              {chat.username}

            </div>

          );

        })}

        <button

          onClick={() => setShowNewChat((previous) => !previous)}

          style={{ marginTop: "20px", padding: "10px" }}

        >

          + New Chat

        </button>

        {showNewChat && (

          <div style={{ marginTop: "15px" }}>

            <input

              value={newUsername}

              onChange={(event) => setNewUsername(event.target.value)}

              onKeyDown={(event) => {

                if (event.key === "Enter") void startNewChat();

              }}

              placeholder="Username"

              style={{

                width: "100%",

                padding: "8px",

                boxSizing: "border-box",

              }}

            />

            <button
              className="chat-button"
               onClick={() => void startNewChat()}
               style={{ marginTop: "8px", padding: "8px" }}
            >
              Start Chat
            </button>
          </div>
        )}

      </aside>

      <main className="chat-main">

        <header className="chat-header">

          <h2 style={{ margin: 0 }}>

            {selectedChat

              ? `Chat with ${selectedChat.username}`

              : "Select a conversation"}

          </h2>

          {selectedChat && (

            <div

              className="chat-presence"

            >

              {selectedPresence?.status === "online"

                ? "🟢 Online"

                : selectedPresence?.status === "offline"

                ? formatLastSeen(selectedPresence.last_seen)

                : "Status unavailable"}

            </div>

          )}

        </header>

        <section
          ref={chatContainerRef}
          className="chat-messages"
        >

          {!selectedChat && (

            <p>Select a conversation to start chatting.</p>

          )}

          {selectedChat && !("conversation_id" in selectedChat) && (

            <p>

              No messages yet. Send a message to start this conversation.

            </p>

          )}

          {selectedMessages.map((msg) => {

            const isOutgoing = msg.sender === currentUsername;

            return (

              <div
                className="message-row"
                style={{
                  display: "flex",
                  justifyContent: isOutgoing ? "flex-end" : "flex-start",
                  marginBottom: 12,
                }}
              >
                <div className={`message-bubble ${isOutgoing ? "outgoing" : ""}`}>

                  <div

                    style={{

                      fontSize: "12px",

                      color: "#666",

                      marginBottom: "4px",

                    }}

                  >

                    {isOutgoing ? "You" : msg.sender}

                  </div>

                  <div style={{ whiteSpace: "pre-wrap" }}>

                    {msg.content}

                  </div>

                  <div

                    style={{

                      display: "flex",

                      alignItems: "center",

                      justifyContent: "flex-end",

                      gap: "6px",

                      marginTop: "5px",

                      fontSize: "11px",

                      color: "#666",

                    }}

                  >

                    {msg.created_at &&

                      new Date(msg.created_at).toLocaleTimeString([], {

                        hour: "2-digit",

                        minute: "2-digit",

                      })}

                    {isOutgoing && renderMessageStatus(msg.status)}

                  </div>

                </div>

              </div>

            );

          })}

        </section>

        {selectedChat && (

          <footer className="chat-composer">
            <input
              className="chat-input"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Type a message..."
            />


            <button className="chat-button primary" onClick={sendMessage}>
              Send
            </button>

          </footer>

        )}

      </main>

    </div>

  );

}

export default Chat;
