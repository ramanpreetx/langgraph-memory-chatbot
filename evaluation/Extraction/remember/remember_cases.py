REMEMBER_CASES = [

    # PREFERENCES

    {
        "input": "Remember that I prefer PyTorch over TensorFlow.",
        "expected": [
            {
                "memory": "User prefers PyTorch over TensorFlow.",
                "type": "preference",
            }
        ],
    },

    {
        "input": "Please remember that I like explanations with step-by-step reasoning.",
        "expected": [
            {
                "memory": "User prefers step-by-step explanations.",
                "type": "preference",
            }
        ],
    },

    {
        "input": "Remember, I prefer working with Python for my machine learning projects.",
        "expected": [
            {
                "memory": "User prefers Python for machine learning projects.",
                "type": "preference",
            }
        ],
    },

    {
        "input": "Can you remember that I don't like overly complicated solutions?",
        "expected": [
            {
                "memory": "User prefers simple solutions and dislikes unnecessary complexity.",
                "type": "preference",
            }
        ],
    },

    {
        "input": "Remember that I prefer concise answers unless I specifically ask for a deep explanation.",
        "expected": [
            {
                "memory": "User prefers concise answers unless they ask for a detailed explanation.",
                "type": "preference",
            }
        ],
    },

    # GOALS

    {
        "input": "Remember that my goal is to get an ML internship.",
        "expected": [
            {
                "memory": "User's goal is to get an ML internship.",
                "type": "goal",
            }
        ],
    },

    {
        "input": "Please remember that I want to become an AI engineer.",
        "expected": [
            {
                "memory": "User wants to become an AI engineer.",
                "type": "goal",
            }
        ],
    },

    {
        "input": "Remember that I want to improve my deep learning skills this year.",
        "expected": [
            {
                "memory": "User's goal is to improve their deep learning skills.",
                "type": "goal",
            }
        ],
    },

    {
        "input": "Remember this: I want to build strong NLP and LLM projects for my portfolio.",
        "expected": [
            {
                "memory": "User wants to build strong NLP and LLM projects for their portfolio.",
                "type": "goal",
            }
        ],
    },

    # PROJECTS

    {
        "input": "Remember that I'm building BERT from scratch using PyTorch.",
        "expected": [
            {
                "memory": "User is building BERT from scratch using PyTorch.",
                "type": "project",
            }
        ],
    },

    {
        "input": "Please remember that my current project is a medical RAG chatbot.",
        "expected": [
            {
                "memory": "User is working on a medical RAG chatbot.",
                "type": "project",
            }
        ],
    },

    {
        "input": "Remember that I'm working on a LangGraph chatbot with long-term and short-term memory.",
        "expected": [
            {
                "memory": "User is working on a LangGraph chatbot with long-term and short-term memory.",
                "type": "project",
            }
        ],
    },

    {
        "input": "Remember that I'm implementing a Transformer from scratch in PyTorch.",
        "expected": [
            {
                "memory": "User is implementing a Transformer from scratch in PyTorch.",
                "type": "project",
            }
        ],
    },

    # FACTS

    {
        "input": "Remember that I'm a final-year B.Tech student studying AI and machine learning.",
        "expected": [
            {
                "memory": "User is a final-year B.Tech student studying AI and machine learning.",
                "type": "fact",
            }
        ],
    },

    {
        "input": "Please remember that I use an RTX 2050 laptop GPU.",
        "expected": [
            {
                "memory": "User uses an RTX 2050 laptop GPU.",
                "type": "fact",
            }
        ],
    },

    {
        "input": "Remember that I usually code using Python 3.10.",
        "expected": [
            {
                "memory": "User usually codes using Python 3.10.",
                "type": "fact",
            }
        ],
    },

    {
        "input": "Remember that I have already implemented a Transformer from scratch.",
        "expected": [
            {
                "memory": "User has already implemented a Transformer from scratch.",
                "type": "fact",
            }
        ],
    },

    # NEGATIVE / NO DURABLE MEMORY
   
    {
        "input": "Remember to explain what attention is when we discuss Transformers.",
        "expected": [],
    },

    {
        "input": "Remember to show me the code for this later.",
        "expected": [],
    },

    {
        "input": "Remember to explain the difference between BERT and GPT.",
        "expected": [],
    },

    {
        "input": "Remember to explain this concept in simple terms.",
        "expected": [],
    },

    {
        "input": "Remember to continue from where we left off tomorrow.",
        "expected": [],
    },

    {
        "input": "Remember to help me debug this error later.",
        "expected": [],
    },

    {
        "input": "Remember to compare these two models for me.",
        "expected": [],
    },

    {
        "input": "Remember to tell me how BERT pretraining works.",
        "expected": [],
    },
]