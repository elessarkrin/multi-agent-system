
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

# Define log levels with custom names for better visibility in agent system
TRACE = 5  # More detailed than DEBUG
logging.addLevelName(TRACE, "TRACE")

class AgentLogger:
    """
    Centralized logger for the multi-agent system that tracks data flow between agents.
    Provides consistent logging format and multiple output options.
    """

    def __init__(
            self,
            agent_name: str,
            log_level: int = logging.INFO,
            log_file: Optional[str] = None,
            console_output: bool = True,
            max_file_size: int = 5 * 1024 * 1024,  # 5MB
            backup_count: int = 3
    ):

        """
        Initialize a logger for a specific agent.
        
        Args:
            agent_name: Name of the agent (used as logger name)
            log_level: Minimum log level to record
            log_file: Optional path to log file
            console_output: Whether to output logs to console
        """
        self.agent_name = agent_name
        self.logger = logging.getLogger(agent_name)
        self.logger.setLevel(log_level)
        self.logger.propagate = False
        
        # Clear any existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s \t %(name)s \t %(levelname)s \t %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add console handler if requested
        if console_output:
            console = logging.StreamHandler(sys.stdout)
            console.setFormatter(formatter)
            self.logger.addHandler(console)
            
        # Add file handler if specified
        if log_file:
            # Create logs directory if it doesn't exist
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            # Use RotatingFileHandler instead of FileHandler
            file_handler = RotatingFileHandler(
                filename=log_file,
                maxBytes=max_file_size,  # 5MB
                backupCount=backup_count,
                delay=True  # Only create the file when first record is emitted
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def trace(self, msg, *args, **kwargs):
        """Log detailed trace information (more granular than debug)"""
        self.logger.log(TRACE, msg, *args, **kwargs)
        
    def data_in(self, data_source: str, data_description: str, data=None):
        """Log data coming into the agent"""
        msg = f"DATA IN from {data_source}: {data_description}"
        if data is not None and self.logger.level <= logging.DEBUG:
            msg += f"\n{data}"
        self.logger.info(msg)
        
    def data_out(self, data_target: str, data_description: str, data=None):
        """Log data going out from the agent"""
        msg = f"DATA OUT to {data_target}: {data_description}"
        if data is not None and self.logger.level <= logging.DEBUG:
            msg += f"\n{data}"
        self.logger.info(msg)
        
    def process_step(self, step_name: str, description: str):
        """Log a processing step within the agent"""
        self.logger.info(f"PROCESS STEP '{step_name}': {description}")
        
    def decision(self, decision_point: str, outcome: str, reasoning: Optional[str] = None):
        """Log a decision made by the agent"""
        msg = f"DECISION at '{decision_point}': {outcome}"
        if reasoning:
            msg += f" - Reasoning: {reasoning}"
        self.logger.info(msg)
    
    # Delegate standard logging methods to the internal logger
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
        
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
        
    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)


def get_system_logger(log_dir: Optional[str] = None, log_level: int = logging.INFO):
    """
    Create a central system logger that tracks overall multi-agent workflow
    
    Args:
        log_dir: Directory to store logs (if None, only console logging is used)
        log_level: Minimum log level to record
    
    Returns:
        AgentLogger: Configured system logger
    """
    if log_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"system_{timestamp}.log")
    else:
        log_file = None
        
    return AgentLogger(
        agent_name="SystemCoordinator",
        log_level=log_level,
        log_file=log_file
    )
