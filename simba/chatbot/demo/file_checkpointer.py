import json
import os
from typing import Any, AsyncIterator, Dict, Iterator, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple

class FileCheckpointSaver(BaseCheckpointSaver):
    """A simple file-based checkpoint saver for local development persistence."""
    
    def __init__(self, file_path: str = "simba_memory.json"):
        super().__init__()
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                json.dump({}, f)

    def _load(self) -> Dict:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save(self, data: Dict):
        with open(self.file_path, "w") as f:
            json.dump(data, f, default=str, indent=2)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        data = self._load()
        thread_data = data.get(thread_id)
        
        if not thread_data:
            return None
            
        # Simplistic implementation: returns the latest checkpoint
        # In real implementation, handle thread_ts properly
        latest_ts = None
        latest_checkpoint = None
        latest_metadata = None
        
        for ts, record in thread_data.items():
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
                latest_checkpoint = record["checkpoint"]
                latest_metadata = record["metadata"]
        
        if not latest_checkpoint:
            return None
            
        # Deserialize (very roughly, assuming dicts)
        # Note: Proper serialization of langgraph Checkpoint needed usually.
        # But for 'messages', simple JSON might drop types (HumanMessage vs dict).
        # We might rely on LangGraph's internal serdes if passing bytes.
        
        # Actually, BaseCheckpointSaver expects explicit get/put.
        # This simple JSON implementation is tricky due to object serialization.
        # A easier way might be pickle.
        pass
        
    # Standard pickle implementation is easier
    
import pickle

class PickleCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, file_path: str = "simba_memory.pkl"):
        super().__init__()
        self.file_path = file_path

    def _load_all(self):
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}

    def _save_all(self, data):
        with open(self.file_path, "wb") as f:
            pickle.dump(data, f)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        all_data = self._load_all()
        if thread_id not in all_data:
            return None
        
        thread_data = all_data[thread_id]
        # Get latest
        if not thread_data: return None
        
        # Sort by key (ts)
        latest_ts = sorted(thread_data.keys())[-1]
        checkpoint, metadata = thread_data[latest_ts]
        
        # parent config? 
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "thread_ts": latest_ts}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None 
        )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Async version of get_tuple"""
        return self.get_tuple(config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> RunnableConfig:
        """Async version of put"""
        return self.put(config, checkpoint, metadata, new_versions)
        
    async def aput_writes(self, config: RunnableConfig, writes: list, task_id: str) -> None:
        """Async version of put_writes"""
        pass

    def list(self, config: Optional[RunnableConfig], *, filter: Optional[Dict[str, Any]] = None, before: Optional[RunnableConfig] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        # Minimal implementation
        yield from []

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["id"] # Use checkpoint ID as timestamp/key
        
        all_data = self._load_all()
        if thread_id not in all_data:
            all_data[thread_id] = {}
            
        all_data[thread_id][thread_ts] = (checkpoint, metadata)
        self._save_all(all_data)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": thread_ts,
            }
        }

    def put_writes(self, config: RunnableConfig, writes: list, task_id: str) -> None:
        pass # Not implementing writes persistence for now (assume simple flow)
