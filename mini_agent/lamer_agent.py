"""Enhanced Agent with LaMer-inspired Meta-RL capabilities."""

import asyncio
import time
from pathlib import Path
from typing import List, Optional

from .agent import Agent  # Import original Agent
from .reflection import ReflectionSystem, MetaLearningSystem, ExecutionEpisode
from .schema import Message


class LaMerAgent(Agent):
    """Enhanced agent with Meta-RL inspired exploration and reflection capabilities."""
    
    def __init__(
        self,
        llm_client,
        system_prompt: str,
        tools: list,
        max_steps: int = 50,
        workspace_dir: str = "./workspace",
        token_limit: int = 80000,
        enable_reflection: bool = True,
        enable_meta_learning: bool = True,
    ):
        super().__init__(llm_client, system_prompt, tools, max_steps, workspace_dir, token_limit)
        
        self.enable_reflection = enable_reflection
        self.enable_meta_learning = enable_meta_learning
        
        if enable_reflection:
            self.reflection_system = ReflectionSystem(
                llm_client, 
                reflection_dir=str(Path(workspace_dir) / "reflections")
            )
            
        if enable_meta_learning:
            self.meta_learning_system = MetaLearningSystem(
                self.reflection_system if enable_reflection else None
            )
            
        # Track current task for episode creation
        self.current_task_description: str = ""
        self.task_start_time: float = 0
        
    def add_user_message(self, content: str):
        """Add a user message to history and track as current task."""
        self.current_task_description = content
        self.task_start_time = time.time()
        super().add_user_message(content)
        
    async def run(self) -> str:
        """Execute enhanced agent loop with reflection and meta-learning."""
        # Get exploration guidance if enabled
        exploration_guidance = ""
        if self.enable_meta_learning and self.current_task_description:
            exploration_guidance = self.meta_learning_system.get_exploration_guidance(
                self.current_task_description
            )
            
        # Add exploration guidance to system context if available
        if exploration_guidance:
            guidance_message = Message(
                role="user",
                content=f"[Exploration Guidance]\n{exploration_guidance}"
            )
            # Insert after system prompt but before user message
            if len(self.messages) >= 2:
                self.messages.insert(1, guidance_message)
            else:
                self.messages.append(guidance_message)
                
        # Get relevant reflections if enabled
        relevant_reflections = []
        if self.enable_reflection and self.current_task_description:
            relevant_reflections = self.reflection_system.get_relevant_reflections(
                self.current_task_description
            )
            
        # Add reflections to context if available
        if relevant_reflections:
            reflections_text = "[Past Reflections]\n" + "\n".join(
                f"{i+1}. {ref}" for i, ref in enumerate(relevant_reflections)
            )
            reflections_message = Message(
                role="user", 
                content=reflections_text
            )
            # Insert after system prompt and any exploration guidance
            insert_pos = 1
            if exploration_guidance:
                insert_pos = 2
            self.messages.insert(insert_pos, reflections_message)
            
        # Run original agent loop
        result = await super().run()
        
        # Create execution episode and generate reflections
        if self.enable_reflection:
            success = not (result.startswith("❌") or result.startswith("⚠️") or 
                          "couldn't be completed" in result)
                          
            episode = ExecutionEpisode(
                task_description=self.current_task_description,
                messages=self.messages.copy(),
                success=success,
                final_outcome=result,
                execution_time=time.time() - self.task_start_time,
                tools_used=list(set([
                    msg.name for msg in self.messages 
                    if msg.role == "tool" and msg.name
                ]))
            )
            
            # Generate and store reflections
            reflections = await self.reflection_system.add_episode(episode)
            print(f"\n💡 Generated {len(reflections)} reflections for future learning!")
            
            # Update meta-learning strategies if enabled
            if self.enable_meta_learning:
                # Extract strategy updates from reflections
                strategy_update = {
                    'preferred_tools': episode.tools_used,
                    'reflection_guidance': reflections[:3]  # Top 3 reflections
                }
                task_type = self.meta_learning_system._classify_task_type(
                    self.current_task_description
                )
                self.meta_learning_system.update_exploration_strategy(
                    task_type, strategy_update
                )
                
        return result