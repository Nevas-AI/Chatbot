"""
rag.py - RAG Pipeline for Neva Chatbot
========================================
Handles document ingestion, embedding, retrieval, and LLM chat
using Google Gemini API for both embeddings and LLM, with a custom
numpy-based vector store that persists to disk as JSON.

Supports multi-client: each RAGPipeline instance receives explicit
config so multiple clients can have isolated knowledge bases.
"""

import os
import json
import logging
import hashlib
from typing import List, Dict, Optional, Generator

import numpy as np
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class VectorStore:
    """
    Lightweight vector store using numpy for similarity search.
    Persists to disk as JSON for survival across restarts.
    """

    def __init__(self, persist_path: str):
        self.persist_path = persist_path
        self.documents: List[Dict] = []  # [{"id", "content", "metadata", "embedding"}]
        self._load()

    def _load(self) -> None:
        """Load vector store from disk if it exists."""
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
                logger.info(f"Loaded {len(self.documents)} documents from {self.persist_path}")
            except Exception as e:
                logger.warning(f"Could not load vector store: {e}")
                self.documents = []

    def _save(self) -> None:
        """Persist vector store to disk."""
        try:
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(self.documents, f)
            logger.debug(f"Saved {len(self.documents)} documents to {self.persist_path}")
        except Exception as e:
            logger.error(f"Could not save vector store: {e}")

    def add(self, content: str, metadata: dict, embedding: List[float]) -> None:
        """Add a document with its embedding."""
        doc_id = hashlib.md5(content.encode()).hexdigest()
        self.documents.append({
            "id": doc_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding,
        })

    def save(self) -> None:
        """Explicit save after batch operations."""
        self._save()

    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict]:
        """Find the top-k most similar documents using cosine similarity."""
        if not self.documents:
            return []

        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored = []
        for doc in self.documents:
            doc_vec = np.array(doc["embedding"])
            doc_norm = np.linalg.norm(doc_vec)
            if doc_norm == 0:
                continue
            similarity = np.dot(query_vec, doc_vec) / (query_norm * doc_norm)
            scored.append((similarity, doc))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {"content": doc["content"], "metadata": doc["metadata"], "score": float(sim)}
            for sim, doc in scored[:k]
        ]

    def clear(self) -> None:
        """Clear all documents."""
        self.documents = []
        self._save()

    def count(self) -> int:
        """Return the number of documents."""
        return len(self.documents)


class RAGPipeline:
    """
    You are {bot_name}, a friendly and intelligent AI assistant for {company_name},
a Microsoft ERP solutions provider specializing in:

Microsoft Dynamics 365 Business Central
Microsoft Dynamics 365 Finance & Operations
Microsoft Dynamics 365 Sales / CRM


KNOWLEDGE SOURCES (Priority Order)
Answer questions using these sources, in order:

Website content from {company_name} — provided as CONTEXT below
FAQ database — provided as CONTEXT below
Your general knowledge — only for broad ERP/Microsoft questions not covered above


INTELLIGENCE LAYER 1 — INTENT DETECTION
Before responding to any message, silently identify what the user actually wants.
There are four intent types:

Informational — They want to learn something. Give a clear, direct explanation.
Evaluative — They are comparing options or deciding something. Help them decide;
offer a recommendation if possible.
Transactional — They want to take action (book a demo, get pricing, speak to someone).
Move them efficiently toward that action.
Conversational — They are chatting, greeting, or expressing a feeling. Match their
energy; be warm and brief.

Never treat every message as informational. A message like "we're stuck on our current
system and need something better" is transactional + evaluative — not a question to define
ERP for. Respond to what the person actually means, not just the literal words.

INTELLIGENCE LAYER 2 — CONTEXT AWARENESS
Track what has been discussed within this conversation and use it to give smarter answers:

If a user mentioned their industry earlier, tailor your answers to that industry.
If a user said they're on a specific ERP (e.g., SAP, Sage, QuickBooks), factor that
into migration or comparison answers without them needing to repeat it.
If the user has already shown buying intent (asked about pricing, demos, etc.),
you do not need to re-detect it — proceed with lead capture or follow-up directly.
Never ask for information the user has already given in this conversation.

Example: If the user said "we're a 50-person manufacturing firm" three messages ago,
and now asks "what would implementation look like for us?", answer specifically for a
50-person manufacturing firm — don't give a generic answer.

INTELLIGENCE LAYER 3 — DISAMBIGUATION
If a user's message is ambiguous (could mean two different things), do not guess silently.
Ask one short, specific clarifying question before answering.
Good disambiguation:
"Are you asking about Business Central specifically, or ERP in general?"
"Do you mean migration from your current system, or a greenfield implementation?"
Bad disambiguation (too broad, feels like you're stalling):
"Could you tell me more about what you're looking for?"
Only disambiguate when the answer would be meaningfully different depending on
the interpretation. If both interpretations lead to the same answer, just answer.

INTELLIGENCE LAYER 4 — PROACTIVE SUGGESTIONS
At the end of relevant responses, offer 1–2 natural follow-up suggestions that the user
is likely to want next — but only when it genuinely helps them, not after every message.
Format them as short, plain-text prompts the user can act on:
"You might also want to know: how long does a typical Business Central implementation take?"
"Related: I can also explain how Business Central compares to Finance & Operations if that's useful."
Do NOT suggest follow-ups after:

Simple greetings or pleasantries
Closing messages
Responses where you've already asked "anything else?"

Use judgment. The goal is to guide the user toward useful information, not to pad responses.

INTELLIGENCE LAYER 5 — SENTIMENT AWARENESS
Read the emotional tone of the user's message and adjust your response accordingly:

Frustrated or stressed ("we've been struggling", "nothing has worked", "I'm fed up"):
Acknowledge briefly before answering. One sentence of empathy, then move to the solution.
Do not be overly sympathetic — keep it brief and focus on helping.
Example: "That sounds like a frustrating situation. Here's what typically works in cases like yours..."
Excited or enthusiastic ("we're finally moving forward!", "this looks perfect"):
Match their energy. Be warm and encouraging without being sycophantic.
Skeptical or cautious ("I'm not sure this is worth it", "we've tried ERP before and it failed"):
Acknowledge their concern directly. Give honest, specific answers — not sales language.
Example: "That's a fair concern. Here's what typically causes ERP projects to fail, and how to avoid it..."
Neutral / professional: Default tone — clear, friendly, efficient.


INTELLIGENCE LAYER 6 — SMART LEAD QUALIFICATION
When capturing leads, use context already gathered in the conversation to pre-fill
what you know, and only ask for what's missing.
If the user already said their company name is "Acme Ltd" earlier in the chat,
do not ask for it again. Instead:
"To connect you with the right specialist, I just need a couple more details:

Your name
Email address
Contact number

(I already have your company as Acme Ltd — let me know if that's changed!)"
When logging lead markers, include any contextual data already confirmed in the conversation
(industry, company size, current ERP system) as a note:
[LEAD_NAME: <name>]
[LEAD_EMAIL: <email>]
[LEAD_PHONE: <phone>]
[LEAD_COMPANY: <company>]
[LEAD_CONTEXT: <e.g., "50-person manufacturing firm, currently on Sage 200, interested in BC migration">]
The LEAD_CONTEXT field is optional — only include it when meaningful context is available.

WHAT YOU CAN ANSWER
You may answer questions related to:

Microsoft Dynamics 365 (Business Central, Finance & Operations, Sales/CRM)
ERP concepts: implementation, migration, integration, licensing, ROI
{company_name}'s services, pricing enquiries, demos, and support
Microsoft 365 / Azure topics that relate to ERP
General business software selection and deployment

For general questions (e.g., "What is an ERP?") not found in the CONTEXT, use your
own knowledge — only if the topic relates to ERP, Microsoft products, or business software.

GREETINGS & SMALL TALK
Casual greetings ("Hi", "Hello", "Good morning", "How are you?") are never off-topic.
Always respond warmly:

Greet the user back naturally
Briefly introduce yourself and offer to help

Example: "Good morning! I'm {bot_name}, here to help with anything related to
{company_name}'s ERP solutions. How can I assist you today?"

OUT-OF-SCOPE QUESTIONS
If a question is clearly unrelated to ERP, Microsoft Dynamics, or {company_name}'s
services (e.g., cooking, sports, personal advice, entertainment), respond with:
"I'm {bot_name}, {company_name}'s ERP assistant. I'm trained specifically to help with
Microsoft Dynamics 365 and ERP-related questions — that topic is a bit outside my area.
Is there anything ERP-related I can help you with? 😊"
Do NOT treat greetings, thank-yous, or pleasantries as out-of-scope.
When in doubt, err on the side of answering if the topic relates even loosely
to ERP, business software, or Microsoft products.

LEAD CAPTURE
Watch for buying signals such as:

Questions about pricing, cost, or licensing
Requests for demos, trials, or consultations
Interest in implementing or switching ERP systems
"How do I get started?" or "Can your team help?"
Questions about timelines or project scope

When you detect buying interest, respond warmly and ask for any details not
already known from the conversation (see Intelligence Layer 6 above):
"That's great to hear! To connect you with the right {company_name} specialist,
could I grab a few quick details?

Your name
Email address
Contact number
Company name

Our team will get back to you shortly!"
If the user declines to share certain details, respect that and continue
with whatever they are comfortable providing.
LOGGING CAPTURED LEADS
When the user provides their contact details, include your natural response AND
append the following markers at the very end of your message, each on its own line.
Only include markers for fields the user actually provided — never fabricate values.
[LEAD_NAME: <name>]
[LEAD_EMAIL: <email>]
[LEAD_PHONE: <phone>]
[LEAD_COMPANY: <company>]
[LEAD_CONTEXT: <optional — relevant context from the conversation>]
Note: These markers are parsed and hidden by the frontend — they will not be
shown to the user. Your visible response should be natural, for example:
"Thanks, Sarah! A {company_name} consultant will be in touch at sarah@example.com soon.
Feel free to ask me anything else in the meantime! 😊"
[LEAD_NAME: Sarah]
[LEAD_EMAIL: sarah@example.com]
[LEAD_CONTEXT: Retail industry, 80 staff, evaluating Business Central]
If a user shares their details across multiple messages, emit only the markers
for fields received in the current message. Do not re-emit markers from earlier turns.

CLOSING THE CONVERSATION
At the end of responses where you have answered a question or completed a task,
always ask: "Is there anything else I can help you with?"
Exception — closing trigger: If the user's message clearly signals they are
finished (e.g., "no", "nope", "that's all", "I'm done", "thanks, bye"), do NOT
ask anything else. Instead, respond only with:
"Would you like to close this chat? Please type 'yes' to confirm."
If the user then types "yes", respond with a brief, warm farewell and end the conversation.

CONVERSATION STYLE

Keep responses short: 2–3 sentences for simple questions; 4–5 for complex ones.
Lead with the direct answer — no openers like "Great question!" or "Sure thing!"
Never paraphrase or repeat back what the user just said.
Use bullet points only when listing 3 or more items; use prose otherwise.
Be friendly and warm, but prioritise brevity.
Use plain language; avoid jargon unless the user is clearly technical.
Use emojis sparingly — no more than 1 per response (the lead-capture request
is an exception, where formatting aids scannability).
For topics needing more detail, give the short answer first, then offer:
"Want me to go deeper on this?"


CONTACT INFORMATION

Email: {support_email}
Phone: {support_phone}
Business Hours: {business_hours}
Share
"""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the RAG pipeline.

        Args:
            config: Optional dict with client-specific settings. Keys:
                - bot_name, company_name, support_email, support_phone, business_hours
                - collection_name, persist_dir
                - gemini_api_key, llm_model, embedding_model
                If None, falls back to environment variables (legacy single-tenant mode).
        """
        config = config or {}
        self.gemini_api_key = config.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
        self.llm_model = config.get("llm_model", os.getenv("LLM_MODEL", "gemini-2.5-flash"))
        self.embedding_model = config.get("embedding_model", os.getenv("EMBEDDING_MODEL", "gemini-embedding-001"))
        self.persist_dir = config.get("persist_dir", os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))
        self.collection_name = config.get("collection_name", os.getenv("CHROMA_COLLECTION_NAME", "aria_knowledge"))
        self.company_name = config.get("company_name", os.getenv("COMPANY_NAME", "Your Company"))
        self.bot_name = config.get("bot_name", os.getenv("BOT_NAME", "Neva"))
        self.support_email = config.get("support_email", os.getenv("SUPPORT_EMAIL", "support@yourcompany.com"))
        self.support_phone = config.get("support_phone", os.getenv("SUPPORT_PHONE", "+91-XXXXXXXXXX"))
        self.business_hours = config.get("business_hours", os.getenv("BUSINESS_HOURS", "Mon-Fri 9AM-6PM IST"))

        # Chunking parameters (~500 tokens = ~2000 chars, ~50 token overlap = ~200 chars)
        self.chunk_size = 2000
        self.chunk_overlap = 200

        # Initialize vector store
        store_path = os.path.join(self.persist_dir, f"{self.collection_name}.json")
        self.vectorstore = VectorStore(persist_path=store_path)

        # Format system prompt with client info
        self.system_prompt = self.SYSTEM_PROMPT.format(
            bot_name=self.bot_name,
            company_name=self.company_name,
            support_email=self.support_email,
            support_phone=self.support_phone,
            business_hours=self.business_hours,
        )

        # Configure Gemini API
        genai.configure(api_key=self.gemini_api_key)

        logger.info(f"RAG pipeline initialized for '{self.collection_name}' with Gemini AI")

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for a text using Gemini Embedding API."""
        result = genai.embed_content(
            model=f"models/{self.embedding_model}",
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        # Split on paragraph boundaries first, then join into chunks
        separators = ["\n\n", "\n", ". ", " "]

        def split_recursive(text: str, sep_idx: int = 0) -> List[str]:
            if len(text) <= self.chunk_size:
                return [text] if text.strip() else []

            if sep_idx >= len(separators):
                # Force split at chunk_size
                result = []
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                    chunk = text[i:i + self.chunk_size]
                    if chunk.strip():
                        result.append(chunk)
                return result

            sep = separators[sep_idx]
            parts = text.split(sep)

            current_chunk = ""
            result = []
            for part in parts:
                candidate = current_chunk + sep + part if current_chunk else part
                if len(candidate) <= self.chunk_size:
                    current_chunk = candidate
                else:
                    if current_chunk.strip():
                        if len(current_chunk) <= self.chunk_size:
                            result.append(current_chunk)
                        else:
                            result.extend(split_recursive(current_chunk, sep_idx + 1))
                    current_chunk = part

            if current_chunk.strip():
                if len(current_chunk) <= self.chunk_size:
                    result.append(current_chunk)
                else:
                    result.extend(split_recursive(current_chunk, sep_idx + 1))

            return result

        chunks = split_recursive(text)
        return chunks

    def ingest_documents(self, documents: list) -> int:
        """
        Ingest scraped documents into the vector store.

        Args:
            documents: List of ScrapedDocument objects with page_content and metadata

        Returns:
            Number of chunks created and stored
        """
        logger.info(f"Ingesting {len(documents)} documents...")
        total_chunks = 0

        for doc in documents:
            try:
                # Split document into chunks
                chunks = self._chunk_text(doc.page_content)

                for chunk in chunks:
                    if len(chunk.strip()) < 20:
                        continue
                    # Get embedding
                    embedding = self._get_embedding(chunk)
                    # Store in vector store
                    self.vectorstore.add(
                        content=chunk,
                        metadata={
                            **doc.metadata,
                            "priority": "normal",
                            "type": "web_content",
                        },
                        embedding=embedding,
                    )
                    total_chunks += 1

                logger.debug(f"Added {len(chunks)} chunks from {doc.metadata.get('url', 'unknown')}")
            except Exception as e:
                logger.warning(f"Error ingesting document: {str(e)}")
                continue

        # Persist to disk
        self.vectorstore.save()
        logger.info(f"Ingestion complete. Created {total_chunks} chunks.")
        return total_chunks

    def ingest_faqs(self, faq_file_path: str) -> int:
        """
        Load and ingest FAQ data with higher priority metadata.

        Args:
            faq_file_path: Path to the faq.json file

        Returns:
            Number of FAQ entries ingested
        """
        try:
            with open(faq_file_path, "r", encoding="utf-8") as f:
                faqs = json.load(f)
        except FileNotFoundError:
            logger.warning(f"FAQ file not found: {faq_file_path}")
            return 0
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in FAQ file: {faq_file_path}")
            return 0

        logger.info(f"Ingesting {len(faqs)} FAQ entries...")
        count = 0

        for faq in faqs:
            question = faq.get("question", "")
            answer = faq.get("answer", "")

            if question and answer:
                # Combine Q&A for better retrieval
                content = f"Question: {question}\nAnswer: {answer}"
                try:
                    embedding = self._get_embedding(content)
                    self.vectorstore.add(
                        content=content,
                        metadata={
                            "source": "faq",
                            "type": "faq",
                            "priority": "high",
                            "question": question,
                        },
                        embedding=embedding,
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"Error embedding FAQ: {str(e)}")

        self.vectorstore.save()
        logger.info(f"Ingested {count} FAQ entries.")
        return count

    def query(self, question: str, k: int = 5) -> List[Dict]:
        """
        Retrieve the most relevant document chunks for a question.
        FAQ results are prioritized over regular web content.
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(question)

            # Retrieve more results to allow for priority sorting
            results = self.vectorstore.search(query_embedding, k=k * 2)

            # Separate FAQ and regular results
            faq_results = []
            regular_results = []

            for result in results:
                if result["metadata"].get("priority") == "high":
                    faq_results.append(result)
                else:
                    regular_results.append(result)

            # Prioritize FAQ results, then fill with regular results
            prioritized = faq_results + regular_results
            return prioritized[:k]

        except Exception as e:
            logger.error(f"Error querying vector store: {str(e)}")
            return []

    def build_context(self, results: List[Dict]) -> str:
        """Build a context string from retrieval results."""
        if not results:
            return "No relevant information found in the knowledge base."

        context_parts = []
        for i, result in enumerate(results, 1):
            source = result["metadata"].get("source", "unknown")
            source_type = result["metadata"].get("type", "unknown")
            content = result["content"]

            if source_type == "faq":
                context_parts.append(f"[FAQ] {content}")
            else:
                title = result["metadata"].get("title", "")
                context_parts.append(f"[Source: {title or source}]\n{content}")

        return "\n\n---\n\n".join(context_parts)

    def chat(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        """Generate a non-streaming chat response."""
        results = self.query(user_message)
        context = self.build_context(results)
        messages = self._build_messages(user_message, context, chat_history)

        try:
            model = genai.GenerativeModel(
                model_name=self.llm_model,
                system_instruction=self.system_prompt,
            )
            # Convert messages to Gemini format (skip system message)
            gemini_history = []
            for msg in messages[1:-1]:  # skip system and last user message
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(messages[-1]["content"])
            
            final_response = response.text
            
            # Format and append unique references from contexts
            urls = []
            for r in results:
                url = r.get("metadata", {}).get("url")
                if url and url not in urls:
                    urls.append(url)
                    
            if urls:
                final_response += "\n\n**References:**\n"
                for url in urls:
                    final_response += f"- {url}\n"
                    
            return final_response.strip()
        except Exception as e:
            logger.error(f"Error generating chat response: {str(e)}")
            return (
                "I'm sorry, I'm having trouble responding right now. "
                "Please try again in a moment, or contact our team directly at "
                f"{self.support_email} or {self.support_phone}."
            )

    def chat_stream(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        """Generate a streaming chat response (yields tokens)."""
        results = self.query(user_message)
        context = self.build_context(results)
        messages = self._build_messages(user_message, context, chat_history)

        try:
            model = genai.GenerativeModel(
                model_name=self.llm_model,
                system_instruction=self.system_prompt,
            )
            # Convert messages to Gemini format (skip system message)
            gemini_history = []
            for msg in messages[1:-1]:  # skip system and last user message
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(messages[-1]["content"], stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text

            # Append unique references after streaming the message
            urls = []
            for r in results:
                url = r.get("metadata", {}).get("url")
                if url and url not in urls:
                    urls.append(url)
                    
            if urls:
                yield "\n\n**References:**\n"
                for url in urls:
                    yield f"- {url}\n"
        except Exception as e:
            logger.error(f"Error streaming chat response: {str(e)}")
            yield (
                "I'm sorry, I'm having trouble responding right now. "
                "Please try again in a moment, or contact our team directly at "
                f"{self.support_email} or {self.support_phone}."
            )

    def _build_messages(
        self,
        user_message: str,
        context: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Build the messages array for the Gemini API call."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        if chat_history:
            recent_history = chat_history[-10:]
            messages.extend(recent_history)

        user_prompt = (
            f"CONTEXT (use this information to answer the question):\n"
            f"{context}\n\n"
            f"USER QUESTION: {user_message}"
        )
        messages.append({"role": "user", "content": user_prompt})

        return messages

    def clear_collection(self) -> None:
        """Clear all documents from the vector store collection."""
        self.vectorstore.clear()
        logger.info("Vector store collection cleared.")

    def get_collection_stats(self) -> Dict:
        """Get statistics about the current vector store collection."""
        return {
            "total_documents": self.vectorstore.count(),
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir,
        }
