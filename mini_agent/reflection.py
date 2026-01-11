"""Reflection and learning system for Mini-Agent based on LaMer framework."""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .schema import Message


@dataclass
class ExecutionEpisode:
    """Represents a single execution episode/task completion attempt."""
    
    task_description: str
    messages: List[Message]
    success: bool
    final_outcome: str
    execution_time: float
    tools_used: List[str]
    reflections: List[str] = None
    
    def __post_init__(self):
        if self.reflections is None:
            self.reflections = []


class ReflectionSystem:
    """Implements in-context policy adaptation via reflection as described in LaMer paper."""
    
    def __init__(self, llm_client, reflection_dir: str = "./reflections"):
        self.llm = llm_client
        self.reflection_dir = Path(reflection_dir)
        self.reflection_dir.mkdir(parents=True, exist_ok=True)
        self.episodes: List[ExecutionEpisode] = []
        
    async def generate_reflection(self, episode: ExecutionEpisode) -> List[str]:
        """Generate reflections on the execution episode to learn from experience."""
        
        # Build execution summary for reflection
        execution_summary = self._build_execution_summary(episode)
        
        reflection_prompt = f"""You are an AI agent reflecting on your recent task execution to improve future performance. 
Analyze what went well, what could be improved, and extract key lessons learned.

Task: {episode.task_description}
Success: {"Yes" if episode.success else "No"}
Final Outcome: {episode.final_outcome}

Execution Summary:
{execution_summary}

Please provide 3-5 specific reflections that will help you perform better on similar tasks in the future.
Focus on:
1. Tool selection and usage strategies
2. Problem decomposition approaches  
3. Error handling and recovery methods
4. Exploration vs exploitation trade-offs
5. When to ask for clarification vs proceed with assumptions

Format each reflection as a concise bullet point starting with "- ".
"""
        
        try:
            response = await self.llm.generate(
                messages=[
                    Message(role="user", content=reflection_prompt)
                ]
            )
            
            # Parse reflections from response
            reflections = self._parse_reflections(response.content)
            return reflections
            
        except Exception as e:
            print(f"Reflection generation failed: {e}")
            return ["Unable to generate reflection due to error"]
    
    def _build_execution_summary(self, episode: ExecutionEpisode) -> str:
        """Build a concise summary of the execution episode."""
        summary_lines = []
        
        for msg in episode.messages:
            if msg.role == "assistant" and msg.content:
                summary_lines.append(f"ASSISTANT: {msg.content[:200]}...")
            elif msg.role == "tool":
                summary_lines.append(f"TOOL ({msg.name}): {msg.content[:100]}...")
                
        return "\n".join(summary_lines)
    
    def _parse_reflections(self, content: str) -> List[str]:
        """Parse reflections from LLM response."""
        reflections = []
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* ') or line.startswith('• '):
                reflection = line[2:].strip()
                if reflection:
                    reflections.append(reflection)
            elif line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                # Handle numbered lists
                reflection = line.split('.', 1)[1].strip()
                if reflection:
                    reflections.append(reflection)
                    
        return reflections[:5]  # Limit to 5 reflections
    
    async def add_episode(self, episode: ExecutionEpisode):
        """Add an episode and generate reflections for it."""
        # Generate reflections
        reflections = await self.generate_reflection(episode)
        episode.reflections = reflections
        
        # Store episode
        self.episodes.append(episode)
        
        # Save to disk
        self._save_episode(episode)
        
        return reflections
    
    def _save_episode(self, episode: ExecutionEpisode):
        """Save episode to disk for cross-episode learning."""
        timestamp = int(time.time())
        filename = f"episode_{timestamp}.json"
        filepath = self.reflection_dir / filename
        
        # Manually construct episode data to handle Pydantic models properly
        episode_data = {
            'task_description': episode.task_description,
            'success': episode.success,
            'final_outcome': episode.final_outcome,
            'execution_time': episode.execution_time,
            'tools_used': episode.tools_used,
            'reflections': episode.reflections,
        }
        # Convert messages to dict format for serialization
        episode_data['messages'] = [
            {
                'role': msg.role,
                'content': msg.content,
                'tool_calls': [tc.model_dump() for tc in msg.tool_calls] if msg.tool_calls else None,
                'tool_call_id': msg.tool_call_id,
                'name': msg.name,
                'thinking': msg.thinking
            } for msg in episode.messages
        ]
        
        with open(filepath, 'w') as f:
            json.dump(episode_data, f, indent=2, ensure_ascii=False)
    
    def get_relevant_reflections(self, current_task: str, max_reflections: int = 3) -> List[str]:
        """Get relevant reflections from past episodes for the current task."""
        if not self.episodes:
            return []
            
        # Simple relevance scoring based on task description similarity
        # In a more advanced implementation, this could use embeddings
        relevant_reflections = []
        
        for episode in reversed(self.episodes[-10:]):  # Look at last 10 episodes
            if episode.reflections:
                # Add all reflections from successful episodes, or partial from failed
                if episode.success:
                    relevant_reflections.extend(episode.reflections)
                else:
                    # Only add first 2 reflections from failed episodes
                    relevant_reflections.extend(episode.reflections[:2])
                    
        return relevant_reflections[:max_reflections]


class MetaLearningSystem:
    """Implements cross-episode training framework for exploration strategy development."""
    
    def __init__(self, reflection_system: ReflectionSystem):
        self.reflection_system = reflection_system
        self.exploration_strategies = {}
        
    def update_exploration_strategy(self, task_type: str, strategy_update: Dict[str, Any]):
        """Update exploration strategy based on cross-episode learning."""
        if task_type not in self.exploration_strategies:
            self.exploration_strategies[task_type] = {
                'preferred_tools': [],
                'exploration_depth': 2,
                'retry_threshold': 3,
                'reflection_guidance': []
            }
            
        # Update strategy based on new insights
        self.exploration_strategies[task_type].update(strategy_update)
        
    def get_exploration_guidance(self, task_description: str) -> str:
        """Get exploration guidance based on task type and past learning."""
        # Simple task type classification
        task_type = self._classify_task_type(task_description)
        
        if task_type in self.exploration_strategies:
            strategy = self.exploration_strategies[task_type]
            guidance = f"Based on past experience with similar tasks:\n"
            
            if strategy['preferred_tools']:
                guidance += f"- Consider using these tools first: {', '.join(strategy['preferred_tools'])}\n"
            if strategy['reflection_guidance']:
                guidance += "- Lessons learned:\n"
                for lesson in strategy['reflection_guidance'][:2]:
                    guidance += f"  • {lesson}\n"
                    
            return guidance
            
        return ""
    
    def _classify_task_type(self, task_description: str) -> str:
        """Classify task into types for strategy application."""
        task_lower = task_description.lower()
        
        if any(word in task_lower for word in ['file', 'read', 'write', 'edit', 'create']):
            return 'file_operations'
        elif any(word in task_lower for word in ['web', 'browser', 'url', 'website']):
            return 'web_browsing'
        elif any(word in task_lower for word in ['code', 'programming', 'script']):
            return 'coding'
        elif any(word in task_lower for word in ['analyze', 'extract', 'process']):
            return 'data_analysis'
        else:
            return 'general'