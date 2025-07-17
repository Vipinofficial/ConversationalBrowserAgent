import asyncio
import json
import re
import time
import base64
import io
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import os
from pathlib import Path
import shutil

# External dependencies
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import streamlit as st
from PIL import Image
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    ERROR = "error"

@dataclass
class BrowserAction:
    """Represents a browser action to be performed"""
    action_type: str  # click, type, navigate, scroll, wait, screenshot, select, extract, switch_frame
    target: str = ""  # CSS selector, URL, or frame selector
    text: str = ""    # Text to type or select
    description: str = ""  # Human-readable description
    delay: float = 1.0    # Delay after action
    value: Optional[Any] = None  # Additional data (e.g., for select options or extracted data)

@dataclass
class ConversationMessage:
    """Represents a message in the conversation"""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    screenshot: Optional[str] = None  # base64 encoded screenshot
    action: Optional[BrowserAction] = None

class OpenRouterClient:
    """Client for OpenRouter API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "AI Browser Agent"
        }
    
    def generate_response(self, messages: List[Dict], model: str = "anthropic/claude-3.5-sonnet") -> str:
        """Generate response using OpenRouter API"""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1500,
                    "temperature": 0.7
                }
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenRouter API error: {response.text}")
                return "I apologize, but I'm having trouble processing your request right now."
        except Exception as e:
            logger.error(f"OpenRouter API exception: {e}")
            return "I encountered an error while processing your request."
    
    def analyze_intent(self, user_input: str, conversation_history: List[Dict]) -> Dict:
        """Analyze user intent and determine required browser actions"""
        system_prompt = """You are an AI browser automation agent. Your job is to understand user requests and determine what browser actions are needed.

Given a user request, analyze it and respond with a JSON object containing:
{
    "intent": "description of what the user wants",
    "actions": [
        {
            "action_type": "navigate|click|type|scroll|wait|screenshot|select|extract|switch_frame",
            "target": "URL or CSS selector or frame selector",
            "text": "text to type or select (if applicable)",
            "description": "human-readable description of this action",
            "value": "additional data if needed (e.g., select option value or extraction details)"
        }
    ],
    "requires_info": ["list of information needed from user"],
    "response": "conversational response to the user"
}

Support a wide range of browser automation tasks, including but not limited to:
- Navigating to websites
- Filling forms (text inputs, dropdowns, checkboxes)
- Clicking buttons or links
- Sending emails
- Searching for information
- Taking screenshots
- Extracting text or data from elements
- Handling iframes
- Scrolling to specific elements
- Selecting options from dropdowns

Be precise with CSS selectors and provide conversational, helpful responses. If the request is ambiguous, ask for clarification in the 'requires_info' field.

Examples:
- User: "send email to test@example.com about meeting"
  Response: {
    "intent": "send an email",
    "actions": [
      {"action_type": "navigate", "target": "https://mail.google.com", "description": "Navigate to Gmail"},
      {"action_type": "wait", "target": "", "delay": 2.0, "description": "Wait for page load"}
    ],
    "requires_info": ["email address", "password", "email subject", "email body"],
    "response": "I'll help you send an email. Please provide your Gmail address, password (use a test account), subject, and email body."
  }
- User: "search for Python tutorials"
  Response: {
    "intent": "perform web search",
    "actions": [
      {"action_type": "navigate", "target": "https://www.google.com", "description": "Navigate to Google"},
      {"action_type": "type", "target": "input[name='q']", "text": "Python tutorials", "description": "Enter search query"},
      {"action_type": "click", "target": "input[name='btnK']", "description": "Click search button"},
      {"action_type": "wait", "target": "", "delay": 2.0, "description": "Wait for results"}
    ],
    "requires_info": [],
    "response": "Searching for Python tutorials on Google."
  }
- User: "extract the main headline from bbc.com"
  Response: {
    "intent": "extract text from website",
    "actions": [
      {"action_type": "navigate", "target": "https://www.bbc.com", "description": "Navigate to BBC"},
      {"action_type": "extract", "target": "h1", "description": "Extract main headline"}
    ],
    "requires_info": [],
    "response": "Extracting the main headline from BBC."
  }
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User request: {user_input}"}
        ]
        
        # Add conversation history for context
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            messages.append(msg)
        
        response = self.generate_response(messages)
        
        try:
            # Try to parse JSON response
            intent_data = json.loads(response)
            logger.debug(f"Intent analysis response: {intent_data}")
            return intent_data
        except json.JSONDecodeError:
            logger.error(f"Failed to parse OpenRouter response: {response}")
            return {
                "intent": "unclear request",
                "actions": [],
                "requires_info": ["Please clarify your request with more details."],
                "response": "I'm sorry, I didn't understand your request. Could you provide more details?"
            }

class BrowserController:
    """Controls browser automation with Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.is_initialized = False
        self.current_frame = None
        self.user_data_dir = Path("./browser_data")  # Directory for persistent context
        
    async def initialize(self, headless: bool = False):
        """Initialize browser with persistent context"""
        try:
            self.playwright = await async_playwright().start()
            # Create user data directory if it doesn't exist
            os.makedirs(self.user_data_dir, exist_ok=True)
            logger.debug(f"User data directory created at: {self.user_data_dir}")
            
            try:
                # Launch browser with persistent context
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=headless,
                    channel='chrome',
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox'
                    ],
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                logger.info("Successfully launched Chrome browser with persistent context")
            except Exception as chrome_error:
                logger.warning(f"Failed to launch Chrome browser: {chrome_error}. Falling back to bundled Chromium.")
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--no-sandbox'
                    ],
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                logger.info("Successfully launched bundled Chromium browser with persistent context")
            
            self.page = await self.context.new_page()
            self.is_initialized = True
            # Log cookies to verify session persistence
            cookies = await self.context.cookies()
            logger.debug(f"Initial cookies in context: {cookies}")
            logger.info("Browser initialized successfully with persistent context")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise e
    
    async def take_screenshot(self) -> str:
        """Take screenshot and return base64 encoded string"""
        if not self.page:
            return ""
            
        try:
            screenshot_bytes = await self.page.screenshot(full_page=True, timeout=10000)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            return screenshot_b64
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return ""
    
    async def execute_action(self, action: BrowserAction) -> Tuple[bool, str]:
        """Execute a browser action"""
        if not self.page:
            return False, "Browser not initialized"
        
        try:
            if action.action_type == "navigate":
                await self.page.goto(action.target, timeout=30000)
                await self.page.wait_for_load_state("domcontentloaded", timeout=30000)
                # Log cookies after navigation
                cookies = await self.context.cookies()
                logger.debug(f"Cookies after navigation to {action.target}: {cookies}")
                return True, f"Navigated to {action.target}"
                
            elif action.action_type == "click":
                await self.page.wait_for_selector(action.target, timeout=10000)
                await self.page.click(action.target)
                return True, f"Clicked on {action.target}"
                
            elif action.action_type == "type":
                await self.page.wait_for_selector(action.target, timeout=10000)
                await self.page.fill(action.target, action.text)
                return True, f"Typed '{action.text}' into {action.target}"
                
            elif action.action_type == "scroll":
                if action.target:
                    await self.page.locator(action.target).scroll_into_view_if_needed(timeout=10000)
                    return True, f"Scrolled to element {action.target}"
                else:
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    return True, "Scrolled to bottom of page"
                
            elif action.action_type == "wait":
                await self.page.wait_for_timeout(int(action.delay * 1000))
                return True, f"Waited for {action.delay} seconds"
                
            elif action.action_type == "screenshot":
                return True, "Screenshot taken"
                
            elif action.action_type == "select":
                await self.page.wait_for_selector(action.target, timeout=10000)
                await self.page.select_option(action.target, value=action.text)
                return True, f"Selected option '{action.text}' in {action.target}"
                
            elif action.action_type == "extract":
                await self.page.wait_for_selector(action.target, timeout=10000)
                element = await self.page.query_selector(action.target)
                text = await element.text_content() if element else ""
                return True, f"Extracted text: {text}"
                
            elif action.action_type == "switch_frame":
                frame = self.page.frame_locator(action.target)
                self.current_frame = frame
                return True, f"Switched to iframe {action.target}"
                
            else:
                return False, f"Unknown action type: {action.action_type}"
                
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            try:
                await self.page.reload(timeout=30000)
                return False, f"Action failed: {str(e)}. Page reloaded for retry."
            except:
                return False, f"Action failed: {str(e)}. Could not recover."
    
    async def get_page_info(self) -> Dict:
        """Get current page information"""
        if not self.page:
            return {}
        
        try:
            return {
                "url": self.page.url,
                "title": await self.page.title(),
                "ready_state": await self.page.evaluate("document.readyState")
            }
        except Exception as e:
            logger.error(f"Failed to get page info: {e}")
            return {}
    
    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
            self.is_initialized = False
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.error(f"Browser cleanup failed: {e}")

class ConversationalBrowserAgent:
    """Main conversational browser agent"""
    
    def __init__(self, openrouter_api_key: str):
        self.openrouter = OpenRouterClient(openrouter_api_key)
        self.browser = BrowserController()
        self.state = AgentState.IDLE
        self.conversation_history: List[Dict] = []
        self.current_task = None
        self.task_context = {}
        
    async def initialize(self):
        """Initialize the agent"""
        await self.browser.initialize(headless=False)
        self.state = AgentState.IDLE
        
    async def process_user_input(self, user_input: str) -> ConversationMessage:
        """Process user input and return response with potential screenshot"""
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Check for email credentials if needed
        if "send email" in user_input.lower() and not self.task_context.get("email_credentials"):
            self.state = AgentState.WAITING_FOR_INPUT
            return ConversationMessage(
                role="assistant",
                content="Please provide your Gmail address and password (use a test account only) to proceed with sending an email.",
                timestamp=datetime.now()
            )
        
        # Check for email details if credentials are provided
        if "send email" in user_input.lower() and self.task_context.get("email_credentials"):
            # Parse user input for email details (basic parsing, improve as needed)
            recipient = re.search(r"to\s+([\w\.-]+@[\w\.-]+)", user_input)
            subject = re.search(r"subject\s+['\"](.+?)['\"]", user_input)
            body = re.search(r"body\s+['\"](.+?)['\"]", user_input)
            
            if not (recipient and subject and body):
                self.state = AgentState.WAITING_FOR_INPUT
                return ConversationMessage(
                    role="assistant",
                    content="Please provide the recipient's email, subject, and body. Example: 'Send email to test@example.com, subject \"Meeting\", body \"Let's meet tomorrow.\"'",
                    timestamp=datetime.now()
                )
            self.task_context["email_details"] = {
                "recipient": recipient.group(1),
                "subject": subject.group(1),
                "body": body.group(1)
            }
        
        # Analyze intent
        self.state = AgentState.THINKING
        intent_data = self.openrouter.analyze_intent(user_input, self.conversation_history)
        
        # Check if we need more information
        if intent_data.get("requires_info"):
            self.state = AgentState.WAITING_FOR_INPUT
            response_msg = ConversationMessage(
                role="assistant",
                content=intent_data["response"],
                timestamp=datetime.now()
            )
            return response_msg
        
        # Execute browser actions
        self.state = AgentState.ACTING
        response_content = intent_data["response"]
        screenshot = None
        extracted_data = []
        
        if intent_data.get("actions"):
            for action_data in intent_data["actions"]:
                action = BrowserAction(
                    action_type=action_data["action_type"],
                    target=action_data.get("target", ""),
                    text=action_data.get("text", ""),
                    description=action_data.get("description", ""),
                    value=action_data.get("value", None)
                )
                
                # Override action text with stored credentials for email tasks
                if "send email" in user_input.lower() and self.task_context.get("email_credentials"):
                    if action.target == "input#identifierId":
                        action.text = self.task_context["email_credentials"].get("email", "")
                    elif action.target == "input[type='password']":
                        action.text = self.task_context["email_credentials"].get("password", "")
                    elif action.target == "input[aria-label='To']":
                        action.text = self.task_context["email_details"].get("recipient", "")
                    elif action.target == "input[aria-label='Subject']":
                        action.text = self.task_context["email_details"].get("subject", "")
                    elif action.target == "div[aria-label='Message Body']":
                        action.text = self.task_context["email_details"].get("body", "")
                
                # Execute the action
                success, result = await self.browser.execute_action(action)
                
                if success:
                    response_content += f"\n\n✅ {action.description}: {result}"
                    if action.action_type == "extract":
                        extracted_data.append(result)
                    # Take screenshot after significant actions
                    if action.action_type in ["navigate", "click", "type", "select", "switch_frame"]:
                        screenshot = await self.browser.take_screenshot()
                else:
                    response_content += f"\n\n❌ Failed: {result}"
                    self.state = AgentState.ERROR
                    break
                
                # Add delay between actions
                await asyncio.sleep(action.delay)
        
        # Take final screenshot if we don't have one
        if not screenshot and self.browser.is_initialized:
            screenshot = await self.browser.take_screenshot()
        
        # Add extracted data to response if any
        if extracted_data:
            response_content += "\n\n📋 Extracted Data:\n" + "\n".join(extracted_data)
        
        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response_content
        })
        
        self.state = AgentState.IDLE
        
        return ConversationMessage(
            role="assistant",
            content=response_content,
            timestamp=datetime.now(),
            screenshot=screenshot
        )
    
    async def cleanup(self):
        """Clean up resources"""
        await self.browser.cleanup()

class BrowserAgentApp:
    """Streamlit application for the browser agent"""
    
    def __init__(self):
        self.agent: Optional[ConversationalBrowserAgent] = None
        
        # Initialize session state
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'agent_initialized' not in st.session_state:
            st.session_state.agent_initialized = False
        if 'agent' not in st.session_state:
            st.session_state.agent = None
    
    async def run_coroutine(self, coro):
        """Helper function to run async coroutines in Streamlit"""
        try:
            return await coro
        except Exception as e:
            logger.error(f"Error running coroutine: {e}")
            st.error(f"Error: {e}")
            return None
    
    def run(self):
        """Run the Streamlit application"""
        
        st.set_page_config(
            page_title="AI Browser Control Agent",
            page_icon="🤖",
            layout="wide"
        )
        
        # Custom CSS for better chat interface
        st.markdown("""
        <style>
        .chat-message {
            padding: 1rem;
            border-radius: 0.5rem;
            margin: 0.5rem 0;
            display: flex;
            flex-direction: column;
        }
        .user-message {
            background-color: black;
            margin-left: 20%;
        }
        .assistant-message {
            background-color: black;
            margin-right: 20%;
        }
        .screenshot-container {
            margin: 1rem 0;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            padding: 0.5rem;
        }
        .stTextInput > div > div > input {
            background-color: green;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Header
        st.title("🤖 AI Browser Control Agent")
        st.markdown("*A conversational AI that can control any website through natural language commands*")
        
        # Sidebar for configuration
        with st.sidebar:
            st.header("🔧 Configuration")
            
            # OpenRouter API Key
            openrouter_api_key = st.text_input(
                "OpenRouter API Key",
                type="password",
                help="Enter your OpenRouter API key for AI capabilities"
            )
            
            # Gmail credentials for email tasks
            st.subheader("📧 Gmail Credentials")
            st.warning("⚠️ Use only test accounts! Never real credentials.")
            
            gmail_email = st.text_input("Test Gmail", placeholder="test@gmail.com")
            gmail_password = st.text_input("Password", type="password")
            
            # Initialize agent button
            if st.button("🚀 Initialize Agent", type="primary"):
                if openrouter_api_key:
                    with st.spinner("Initializing browser agent..."):
                        try:
                            # Initialize agent
                            agent = ConversationalBrowserAgent(openrouter_api_key)
                            st.session_state.agent = agent
                            st.session_state.agent_initialized = True
                            st.session_state.openrouter_api_key = openrouter_api_key
                            if gmail_email and gmail_password:
                                st.session_state.agent.task_context["email_credentials"] = {
                                    "email": gmail_email,
                                    "password": gmail_password
                                }
                            # Initialize browser asynchronously
                            asyncio.run(agent.initialize())
                            st.success("✅ Agent initialized! Start chatting below.")
                        except Exception as e:
                            st.error(f"❌ Failed to initialize agent: {e}")
                            logger.error(f"Agent initialization failed: {e}")
                else:
                    st.error("Please provide OpenRouter API key")
            
            # Clear browser data button
            if st.session_state.agent_initialized and st.button("🗑️ Clear Browser Data"):
                with st.spinner("Clearing browser data..."):
                    try:
                        if st.session_state.agent.browser.is_initialized:
                            # Run cleanup asynchronously
                            asyncio.run(self.run_coroutine(st.session_state.agent.cleanup()))
                        shutil.rmtree(st.session_state.agent.browser.user_data_dir, ignore_errors=True)
                        st.success("✅ Browser data cleared. Next session will be fresh.")
                        st.session_state.agent_initialized = False
                        st.session_state.agent = None
                    except Exception as e:
                        st.error(f"❌ Failed to clear browser data: {e}")
                        logger.error(f"Failed to clear browser data: {e}")
            
            # Status indicator
            if st.session_state.agent_initialized:
                st.success("🟢 Agent Ready")
            else:
                st.error("🔴 Agent Not Initialized")
            
            # Example commands
            st.subheader("💡 Example Commands")
            st.markdown("""
            - "Go to Google and search for Python tutorials"
            - "Send email to test@example.com, subject 'Meeting', body 'Let's meet tomorrow'"
            - "Navigate to bbc.com and extract the main headline"
            - "Open example.com and fill out the contact form"
            - "Select 'Large' from the size dropdown on a shopping website"
            - "Take a screenshot of the current page"
            """)
        
        # Main chat interface
        st.header("💬 Chat with your Browser Agent")
        
        # Display conversation history
        for i, message in enumerate(st.session_state.messages):
            with st.container():
                if message["role"] == "user":
                    st.markdown(f"""
                    <div class="chat-message user-message">
                        <strong>You:</strong> {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                
                elif message["role"] == "assistant":
                    st.markdown(f"""
                    <div class="chat-message assistant-message">
                        <strong>🤖 Agent:</strong> {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Display screenshot if available
                    if message.get("screenshot"):
                        st.markdown("**📸 Live Screenshot:**")
                        try:
                            img_data = base64.b64decode(message["screenshot"])
                            img = Image.open(io.BytesIO(img_data))
                            st.image(img, caption="Browser Screenshot", use_column_width=True)
                        except Exception as e:
                            st.error(f"Failed to display screenshot: {e}")
                            logger.error(f"Failed to display screenshot: {e}")
        
        # Chat input
        user_input = st.chat_input("Type your command here... (e.g., 'Go to Google and search for Python tutorials')")
        
        if user_input:
            if not st.session_state.agent_initialized:
                st.error("Please initialize the agent first using the sidebar.")
                return
            
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Process with agent
            with st.spinner("🤖 Agent is working..."):
                try:
                    # Process user input asynchronously
                    response = asyncio.run(self.run_coroutine(st.session_state.agent.process_user_input(user_input)))
                    if response:
                        # Add agent response
                        message_data = {
                            "role": "assistant",
                            "content": response.content,
                            "timestamp": response.timestamp.isoformat()
                        }
                        
                        if response.screenshot:
                            message_data["screenshot"] = response.screenshot
                        
                        st.session_state.messages.append(message_data)
                        
                        # Rerun to show the new message
                        st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error processing command: {e}")
                    logger.error(f"Error in main chat loop: {e}")
        
        # Footer
        st.markdown("---")
        st.markdown("*Built with Streamlit, Playwright, and OpenRouter API*")

def main():
    """Main function to run the application"""
    app = BrowserAgentApp()
    app.run()

if __name__ == "__main__":
    main()