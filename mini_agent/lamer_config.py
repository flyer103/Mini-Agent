"""LaMer configuration for enhanced Mini-Agent capabilities."""

# LaMer Agent Configuration
LAMER_CONFIG = {
    "enable_reflection": True,
    "enable_meta_learning": True,
    "reflection_dir": "./workspace/reflections",
    "max_reflections_per_task": 3,
    "exploration_strategy_update_frequency": 1,  # Update after every episode
}

# System prompt enhancements for LaMer
LAMER_SYSTEM_PROMPT_ADDITIONS = """
## Enhanced Capabilities

You now have access to:

### Past Reflections
- Learn from previous task executions through reflection-based adaptation
- Apply lessons learned to current tasks without retraining

### Exploration Guidance  
- Receive guidance on tool selection and problem-solving strategies based on cross-episode learning
- Optimize exploration vs exploitation trade-offs for better long-term performance

### Meta-Learning
- Adapt your policy in-context based on environment feedback signals
- Develop robust exploration strategies for novel environments

When solving tasks:
1. Consider the exploration guidance provided
2. Apply relevant lessons from past reflections  
3. Use systematic exploration when uncertain
4. Reflect on your approach and adapt as you receive feedback
5. Prioritize long-term success over short-term gains
"""