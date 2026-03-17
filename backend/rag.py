"""
rag.py - RAG Pipeline for Neva Chatbot
========================================
Handles document ingestion, embedding, retrieval, and LLM chat
using Ollama for both embeddings and LLM, with a custom numpy-based
vector store that persists to disk as JSON.

Supports multi-client: each RAGPipeline instance receives explicit
config so multiple clients can have isolated knowledge bases.
"""

import os
import json
import logging
import hashlib
from typing import List, Dict, Optional, Generator

import numpy as np
import ollama
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
    Retrieval Augmented Generation pipeline for the Neva chatbot.

    Supports multi-client: accepts an explicit config dict so each
    client can have its own knowledge base, system prompt, and settings.
    """

    # System prompt template — placeholders filled per-client
    SYSTEM_PROMPT = """You are {bot_name}, a friendly and conversational AI assistant for {company_name},
a Microsoft ERP solutions provider specializing in:
- Microsoft Dynamics 365 Business Central
- Microsoft Dynamics 365 Finance & Operations
- Microsoft Dynamics 365 Sales / CRM

## KNOWLEDGE SOURCES (Priority Order)
You answer questions using the following sources, in this priority order:
1. Website content from {company_name} (highest priority) — provided as CONTEXT below
2. FAQ database provided to you — provided as CONTEXT below
3. Your own general knowledge (only for general ERP/Microsoft questions)

## WHAT YOU CAN ANSWER
You are allowed to answer questions related to:
- Microsoft Dynamics 365 Business Central, Finance & Operations, Sales / CRM
- ERP concepts, implementation, migration, and integration
- {company_name}'s services, pricing enquiries, demos, and support
- General Microsoft 365 / Azure topics that relate to ERP
- FAQs about ERP selection, ROI, deployment, and licensing

If a question is general (e.g., "What is an ERP?") and is NOT in the provided CONTEXT,
use your general knowledge to answer — but only if it is still relevant
to ERP, Microsoft products, or business software topics.

## GREETINGS & SMALL TALK
Casual greetings (e.g., "Hi", "Hello", "Good morning", "Hey there", "How are you?")
are NOT off-topic. Always respond warmly and naturally to greetings:
- Greet the user back in a friendly way
- Briefly introduce yourself and offer to help
- Example: "Good morning! 👋 I'm {bot_name}, here to help with anything related to {company_name}'s ERP solutions. How can I assist you today?"

## WHAT YOU MUST NOT ANSWER
If a user asks something completely unrelated to ERP, Microsoft Dynamics,
or {company_name}'s services (e.g., cooking recipes, sports scores, general coding unrelated to ERP,
personal life advice, entertainment, etc.), respond with:

"I'm {bot_name}, {company_name}'s ERP assistant! I'm specifically trained to help with
Microsoft Dynamics 365 and ERP-related questions. I'm not able to help with
that topic, but I'd love to assist you with anything related to ERP solutions
or {company_name}'s services. 😊"

Do NOT treat casual greetings, thank-yous, or pleasantries as out-of-scope.
Only decline genuinely off-topic knowledge questions.

## LEAD CAPTURE (VERY IMPORTANT)
Monitor the conversation for buying signals such as:
- Asking about pricing, cost, or licensing
- Asking about demos, trials, or consultations
- Expressing interest in implementing or switching ERP
- Asking "how do I get started" or "can your team help"
- Asking about timelines or project scope

When you detect buying interest, naturally and warmly say:

"That's great to hear! To connect you with the right {company_name} specialist,
could I grab a few quick details?
- 👤 Your Name
- 📧 Email Address
- 📞 Contact Number
- 🏢 Company Name

Our team will get back to you shortly!"

If the user provides their details, confirm receipt with:
"Thanks, [Name]! A {company_name} consultant will reach out to you at [email] soon.
In the meantime, feel free to ask me anything else! 😊"

## CLOSING THE CONVERSATION (HIGH PRIORITY)
- If the user explicitly indicates they have no more questions or want to end the chat (e.g., "no", "none", "that's it", "thanks, I'm done"), DO NOT provide a standard response. You MUST respond ONLY with this exact phrase:
"Would you like to close this chat? Please type 'yes' to confirm."
- For ALL OTHER responses, you MUST ALWAYS ask if there is anything else you can help with at the end of your message (e.g., "Is there anything else I can help you with?").

## CONVERSATION STYLE
- **KEEP IT SHORT.** Respond in 2-3 sentences max for simple questions. Only use 4-5 sentences for complex topics.
- Never repeat or rephrase what the user just said back to them.
- Lead with the direct answer — no preamble like "Great question!" or "That's a good question."
- Use bullet points ONLY when listing 3+ items. Use prose for everything else.
- Be friendly and warm, but prioritize brevity over thoroughness.
- Use simple language; avoid jargon unless the user is clearly technical.
- Use emojis sparingly (max 1 per response).
- If the topic needs more detail, give the short answer first, then say "Want me to go deeper into this?"

## CONTACT INFO
- Email: {support_email}
- Phone: {support_phone}
- Business Hours: {business_hours}

## FALLBACK RULE
If you are unsure whether a question is in scope, err on the side of answering
if it relates even loosely to ERP, business software, or Microsoft products.
If it is clearly out of scope, use the decline message above.
"""

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the RAG pipeline.

        Args:
            config: Optional dict with client-specific settings. Keys:
                - bot_name, company_name, support_email, support_phone, business_hours
                - collection_name, persist_dir
                - ollama_base_url, llm_model, embedding_model
                If None, falls back to environment variables (legacy single-tenant mode).
        """
        config = config or {}
        self.ollama_base_url = config.get("ollama_base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
        self.llm_model = config.get("llm_model", os.getenv("LLM_MODEL", "llama3.1"))
        self.embedding_model = config.get("embedding_model", os.getenv("EMBEDDING_MODEL", "nomic-embed-text"))
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

        logger.info(f"RAG pipeline initialized for '{self.collection_name}'")

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for a text using Ollama."""
        response = ollama.embed(model=self.embedding_model, input=text)
        return response["embeddings"][0]

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
            response = ollama.chat(
                model=self.llm_model,
                messages=messages,
            )
            return response["message"]["content"]
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
            stream = ollama.chat(
                model=self.llm_model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                if token:
                    yield token
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
        """Build the messages array for the Ollama API call."""
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
