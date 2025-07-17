# 🤖 Conversational AI Browser Control Agent

A sophisticated AI agent that can control any website through natural language commands, inspired by Proxy by Convergence AI. This agent understands conversational requests and performs browser automation with real-time visual feedback.

## 🎯 Project Overview

This is **NOT** just an email automation tool - it's a foundational technology for AI agents that can control browsers to perform ANY task through natural language conversation.

### Key Features:
- **Conversational Interface**: Chat with the agent like you would with ChatGPT
- **Universal Browser Control**: Can navigate and interact with any website
- **Real-time Screenshots**: See exactly what the browser is doing, embedded in the chat
- **Natural Language Understanding**: Interprets complex commands and breaks them into browser actions
- **Flexible Architecture**: Easily extendable to handle any web-based task

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Chat Interface                     │
├─────────────────────────────────────────────────────────────────────┤
│ ConversationalBrowserAgent                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  OpenRouter     │  │  BrowserController│  │  Intent Analysis    │  │
│  │  API Client     │  │  (Playwright)     │  │  & Action Planning  │  │
│  │  - Claude 3.5   │  │  - Navigation     │  │  - Command Parsing  │  │
│  │  - GPT-4        │  │  - Interaction    │  │  - Context Memory   │  │
│  │  - Reasoning    │  │  - Screenshots    │  │  - Task Planning    │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                     Browser Automation Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │   Navigation    │  │   Form Filling  │  │   Screenshot        │  │
│  │   - goto()      │  │   - fill()      │  │   - capture()       │  │
│  │   - click()     │  │   - select()    │  │   - display()       │  │
│  │   - scroll()    │  │   - submit()    │  │   - embed_in_chat() │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Core Components

### 1. **ConversationalBrowserAgent**
The main orchestrator that:
- Processes natural language commands
- Maintains conversation context
- Coordinates between AI reasoning and browser actions
- Handles error recovery and user feedback

### 2. **OpenRouterClient**
AI-powered intent analysis using:
- Claude 3.5 Sonnet for superior reasoning
- GPT-4 for complex task planning
- Intent recognition and action planning
- Context-aware conversation management

### 3. **BrowserController**
Playwright-based browser automation:
- Headless and visible browser modes
- Real-time screenshot capture
- Robust error handling
- Cross-platform compatibility

### 4. **Real-time Chat Interface**
Streamlit-based conversational UI:
- Screenshots embedded directly in chat
- Natural conversation flow
- Live status updates
- Visual feedback for all actions

## 💬 Example User Interactions

### Email Task
```
User: "Send a leave application email to my manager"
Agent: "I'll help you send that email. What's your Gmail address?"
User: "test@gmail.com"
Agent: "Opening Gmail now..."
[SCREENSHOT: Gmail login page appears in chat]
Agent: "Logging in with your credentials..."
[SCREENSHOT: Gmail inbox appears in chat]
Agent: "When will you be on leave?"
User: "August 15-20"
Agent: "Composing your leave email..."
[SCREENSHOT: Email composition window appears in chat]
Agent: "Email sent successfully!"
[SCREENSHOT: Sent confirmation appears in chat]
```

### Research Task
```
User: "Search for Python tutorials on Google and take screenshots"
Agent: "I'll search for Python tutorials and capture screenshots for you."
[SCREENSHOT: Google homepage]
Agent: "Searching for 'Python tutorials'..."
[SCREENSHOT: Google search results]
Agent: "Here are the Python tutorial results. Would you like me to visit any specific sites?"
```

### Form Filling
```
User: "Fill out the contact form on example.com with my details"
Agent: "I'll navigate to example.com and fill out the contact form."
[SCREENSHOT: example.com homepage]
Agent: "Found the contact form. What details should I fill in?"
User: "Name: John Doe, Email: john@example.com, Message: Interested in your services"
Agent: "Filling out the form now..."
[SCREENSHOT: Completed contact form]
Agent: "Form submitted successfully!"
```

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- OpenRouter API key
- Test Gmail account (for email tasks)

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/ai-browser-control-agent.git
cd ai-browser-control-agent
```

### Step 2: Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Step 3: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
OPENROUTER_API_KEY=your_openrouter_api_key_here
GMAIL_EMAIL=test@gmail.com
GMAIL_PASSWORD=your_test_password_here
```

### Step 4: Run the Application
```bash
streamlit run main.py
```

Open your browser and go to `http://localhost:8501`

## 🔧 Configuration

### OpenRouter API Setup
1. Visit [OpenRouter](https://openrouter.ai/)
2. Create an account and get your API key
3. Add the key to your `.env` file or enter it in the sidebar

### Gmail Configuration
- **CRITICAL**: Use only test Gmail accounts
- Enable "Less secure app access" or use App
