# Changelog

All notable changes to pydata-utils will be documented in this file.

## [1.0.3] - 2026-01-15

### Added

- **GPU Compute Engine**: High-performance GPU-accelerated tensor operations for ML training
- **Distributed Training**: Multi-GPU and distributed compute support with NCCL backend
- **Model Checkpointing**: Automatic model state persistence with remote sync capabilities
- **Training Monitor**: Real-time training progress and metrics logging
- **Experiment State**: Hyperparameter tracking and experiment configuration management
- **GPU Utilities**: Device detection, memory management, and compute optimization
- **Data Preprocessing**: Efficient data loading, transformation, and augmentation pipelines

### Changed

- Refactored core API for ML-focused workflows
- Enhanced data operations with training-specific features
- Improved caching for model weights and training data

## [1.0.2] - 2025-12-20

### Added

- Cache Manager with TTL support for training data
- Data validation against schemas
- Persistent configuration management
- Deep merge utility for config composition

## [1.0.1] - 2025-11-15

### Added

- JSON/CSV load/save operations
- Remote configuration loading
- Parallel processing utilities
- Retry decorator for resilient operations

## [1.0.0] - 2025-10-01

### Added

- Initial release
- Basic data utilities
- File operations
- Utility functions
