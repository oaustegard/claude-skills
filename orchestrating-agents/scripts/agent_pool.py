"""
Agent Pool — Named agents with inter-agent messaging.

Adapted from OpenAI Codex's InterAgentCommunication and SpawnReservation
patterns for stateless API-call environments.

Key concepts:
- AgentPool: manages named ConversationThreads with a shared message board
- Messages between agents can optionally trigger automatic turns
- SpawnReservation: context manager ensuring atomic agent creation with rollback
- Depth limits prevent recursive spawn explosion

Usage:
    from agent_pool import AgentPool

    pool = AgentPool(
        shared_system="You are part of a code review team.",
        max_depth=3
    )

    # Spawn named agents with roles
    pool.spawn("security", system="You are a security expert. " + pool.EXECUTE_MODE)
    pool.spawn("perf", system="You are a performance expert. " + pool.EXECUTE_MODE)

    # Run turns (pending messages auto-injected)
    sec_result = pool.run("security", "Review auth.py for vulnerabilities")

    # Inter-agent messaging
    pool.send("security", to="perf",
              content="Found auth is doing N+1 queries — check perf impact",
              trigger_turn=True)  # auto-runs perf agent with this message

    # Broadcast to all
    pool.broadcast("security", "Auth module uses bcrypt with cost=12")
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from contextlib import contextmanager


# Lazy import to avoid circular deps
def _get_conversation_thread():
    from claude_client import ConversationThread
    return ConversationThread


# ---------------------------------------------------------------------------
# Execute Mode System Prompt (adapted from OpenAI Codex collaboration modes)
# ---------------------------------------------------------------------------

EXECUTE_MODE = """You execute on a well-specified task independently and report results.

Execution rules:
- When information is missing, do NOT ask questions. Make a sensible assumption, state it briefly, and continue.
- Think out loud when it helps evaluate tradeoffs. Keep explanations short and grounded in consequences.
- Think ahead: what else might be needed? How will the result be validated?
- Be mindful of time. Minimize exploration; prefer direct action.
- If something fails, report what failed, what you tried, and what you will do next.
- When done, summarize what you delivered and how to validate it.

If other agents have sent you messages, incorporate their findings into your work.
Do not repeat their analysis — build on it."""


# ---------------------------------------------------------------------------
# Message Types
# ---------------------------------------------------------------------------

@dataclass
class AgentMessage:
    """A message between agents in the pool."""
    author: str
    recipient: str  # "*" for broadcast
    content: str
    trigger_turn: bool = False
    timestamp: float = field(default_factory=time.time)

    def format_for_injection(self) -> str:
        return f"[Message from {self.author}]: {self.content}"


# ---------------------------------------------------------------------------
# Spawn Reservation
# ---------------------------------------------------------------------------

class SpawnReservation:
    """
    Context manager for atomic agent creation.

    Reserves a name in the pool. If the block exits normally, the agent
    is committed. If an exception occurs, the reservation is rolled back.

    Adapted from Codex's SpawnReservation pattern (reserve → commit/drop).

    Usage:
        with pool.reserve("analyst") as res:
            res.configure(system="You analyze data.", model="claude-sonnet-4-6")
            # If this raises, the name is released
        # Agent "analyst" is now live in the pool
    """

    def __init__(self, pool: 'AgentPool', name: str, parent: Optional[str] = None):
        self.pool = pool
        self.name = name
        self.parent = parent
        self.system: Optional[str] = None
        self.model: str = "claude-sonnet-4-6"
        self.max_tokens: int = 4096
        self.temperature: float = 1.0
        self._committed = False

    def configure(self, *, system: str = None, model: str = None,
                  max_tokens: int = None, temperature: float = None):
        """Set agent configuration before commit."""
        if system is not None:
            self.system = system
        if model is not None:
            self.model = model
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if temperature is not None:
            self.temperature = temperature

    def commit(self):
        """Finalize the agent in the pool."""
        ConversationThread = _get_conversation_thread()

        effective_system = self.system or ""
        if self.pool.shared_system:
            effective_system = f"{self.pool.shared_system}\n\n{effective_system}"

        thread = ConversationThread(
            system=effective_system,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            cache_system=True,
        )

        depth = 0
        if self.parent and self.parent in self.pool._depths:
            depth = self.pool._depths[self.parent] + 1

        with self.pool._lock:
            self.pool._agents[self.name] = thread
            self.pool._depths[self.name] = depth
            if self.parent:
                self.pool._children.setdefault(self.parent, []).append(self.name)
        self._committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self._committed:
            self.commit()
        elif exc_type is not None:
            # Rollback: release the reserved name
            with self.pool._lock:
                self.pool._reserved.discard(self.name)
        return False


# ---------------------------------------------------------------------------
# Agent Pool
# ---------------------------------------------------------------------------

class AgentPool:
    """
    Pool of named agents with inter-agent messaging.

    Each agent is a ConversationThread. Messages between agents are queued
    and injected into the recipient's next turn. Messages with
    trigger_turn=True cause an automatic API call to the recipient.

    Args:
        shared_system: System prompt shared across all agents (cached).
        max_agents: Maximum number of concurrent agents (default: 10).
        max_depth: Maximum spawn depth for parent→child chains (default: 3).
        model: Default model for all agents.
    """

    # Expose as class attribute for easy access
    EXECUTE_MODE = EXECUTE_MODE

    def __init__(self, shared_system: str = None, max_agents: int = 10,
                 max_depth: int = 3, model: str = "claude-sonnet-4-6"):
        self.shared_system = shared_system
        self.max_agents = max_agents
        self.max_depth = max_depth
        self.default_model = model

        self._agents: dict[str, object] = {}   # name → ConversationThread
        self._depths: dict[str, int] = {}       # name → spawn depth
        self._children: dict[str, list] = {}    # parent → [child names]
        self._reserved: set[str] = set()        # names currently being spawned
        self._mailbox: list[AgentMessage] = []
        self._lock = threading.Lock()

    # -- Spawn --

    def spawn(self, name: str, *, system: str = None, model: str = None,
              parent: str = None, **kwargs) -> str:
        """
        Create a named agent in the pool.

        Args:
            name: Unique agent name.
            system: Agent-specific system prompt (appended to shared_system).
            model: Model override (default: pool's default).
            parent: Parent agent name (for depth tracking).
            **kwargs: Additional ConversationThread params.

        Returns:
            Agent name.

        Raises:
            ValueError: If name exists, pool is full, or depth exceeded.
        """
        with self._lock:
            if name in self._agents or name in self._reserved:
                raise ValueError(f"Agent '{name}' already exists or is being spawned")
            if len(self._agents) >= self.max_agents:
                raise ValueError(f"Pool full ({self.max_agents} agents)")
            if parent and parent in self._depths:
                if self._depths[parent] + 1 >= self.max_depth:
                    raise ValueError(
                        f"Spawn depth limit ({self.max_depth}) exceeded: "
                        f"parent '{parent}' at depth {self._depths[parent]}"
                    )
            self._reserved.add(name)

        try:
            with self.reserve(name, parent=parent) as res:
                res.configure(
                    system=system,
                    model=model or self.default_model,
                    **{k: v for k, v in kwargs.items()
                       if k in ('max_tokens', 'temperature')}
                )
        finally:
            with self._lock:
                self._reserved.discard(name)

        return name

    @contextmanager
    def reserve(self, name: str, parent: str = None):
        """
        Reserve a name for atomic agent creation.

        Usage:
            with pool.reserve("analyst", parent="lead") as res:
                res.configure(system="...", model="claude-opus-4-6")
        """
        reservation = SpawnReservation(self, name, parent)
        yield reservation

    # -- Messaging --

    def send(self, author: str, *, to: str, content: str,
             trigger_turn: bool = False) -> Optional[str]:
        """
        Send a message from one agent to another.

        Args:
            author: Sending agent name.
            to: Recipient agent name.
            content: Message content.
            trigger_turn: If True, automatically run the recipient with
                          this message (and return the response).

        Returns:
            Recipient's response if trigger_turn=True, else None.
        """
        msg = AgentMessage(
            author=author, recipient=to,
            content=content, trigger_turn=trigger_turn
        )
        with self._lock:
            self._mailbox.append(msg)

        if trigger_turn:
            return self.run(to, f"[Triggered by message from {author}]")
        return None

    def broadcast(self, author: str, content: str, *,
                  exclude: set = None, trigger_turn: bool = False) -> dict:
        """
        Send a message to all other agents.

        Returns:
            Dict of {agent_name: response} for agents that were triggered.
        """
        exclude = (exclude or set()) | {author}
        responses = {}
        for name in list(self._agents.keys()):
            if name not in exclude:
                result = self.send(
                    author, to=name, content=content,
                    trigger_turn=trigger_turn
                )
                if result is not None:
                    responses[name] = result
        return responses

    # -- Execution --

    def _drain_messages(self, agent_name: str) -> list[AgentMessage]:
        """Remove and return all pending messages for an agent."""
        with self._lock:
            pending = [m for m in self._mailbox if m.recipient in (agent_name, "*")]
            self._mailbox = [m for m in self._mailbox
                            if m.recipient not in (agent_name, "*")]
        return pending

    def run(self, agent_name: str, prompt: str, **kwargs) -> str:
        """
        Run a turn for a named agent, injecting any pending messages.

        Pending messages from other agents are prepended to the prompt
        so the agent has full context.

        Args:
            agent_name: Agent to run.
            prompt: User message for this turn.
            **kwargs: Additional send() params.

        Returns:
            Agent's response text.
        """
        if agent_name not in self._agents:
            raise ValueError(f"Agent '{agent_name}' not in pool")

        thread = self._agents[agent_name]

        # Inject pending messages
        pending = self._drain_messages(agent_name)
        if pending:
            msg_block = "\n".join(m.format_for_injection() for m in pending)
            prompt = f"{msg_block}\n\n{prompt}"

        return thread.send(prompt, **kwargs)

    # -- Lifecycle --

    def shutdown(self, agent_name: str):
        """Remove an agent from the pool."""
        with self._lock:
            self._agents.pop(agent_name, None)
            self._depths.pop(agent_name, None)
            self._reserved.discard(agent_name)
            # Remove from parent's children
            for parent, children in self._children.items():
                if agent_name in children:
                    children.remove(agent_name)

    def shutdown_all(self):
        """Remove all agents."""
        with self._lock:
            self._agents.clear()
            self._depths.clear()
            self._children.clear()
            self._reserved.clear()
            self._mailbox.clear()

    # -- Queries --

    def agents(self) -> list[str]:
        """List all active agent names."""
        return list(self._agents.keys())

    def agent_info(self, name: str) -> dict:
        """Get agent metadata."""
        if name not in self._agents:
            raise ValueError(f"Agent '{name}' not in pool")
        return {
            "name": name,
            "depth": self._depths.get(name, 0),
            "children": self._children.get(name, []),
            "pending_messages": sum(
                1 for m in self._mailbox if m.recipient in (name, "*")
            ),
            "turns": len(self._agents[name]),
        }

    def __len__(self):
        return len(self._agents)

    def __contains__(self, name):
        return name in self._agents
