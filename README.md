<h1 align="center">Simba - Your Knowledge Management System</h1>

<p align="center">
<img src="/assets/logo.png" alt="Simba Logo" width="400" height="400"/>
</p>

<p align="center">
<strong>Connect your knowledge to any RAG system</strong>
</p>

<p align="center">
<a href="https://www.producthunt.com/posts/simba-2?embed=true&utm_source=badge-featured&utm_medium=badge&utm_souce=badge-simba&#0045;2" target="_blank"><img src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=863851&theme=light&t=1739449352356" alt="Simba&#0032; - Connect&#0032;your&#0032;Knowledge&#0032;into&#0032;any&#0032;RAG&#0032;based&#0032;system | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" /></a>
</p>

<p align="center">


<a href="https://github.com/GitHamza0206/simba/blob/main/LICENSE">
<img src="https://img.shields.io/github/license/GitHamza0206/simba" alt="License">
</a>
<a href="https://github.com/GitHamza0206/simba/stargazers">
<img src="https://img.shields.io/github/stars/GitHamza0206/simba" alt="Stars">
</a>
<a href="https://github.com/GitHamza0206/simba/network/members">
<img src="https://img.shields.io/github/forks/GitHamza0206/simba" alt="Forks">
</a>
<a href="https://github.com/GitHamza0206/simba/issues">
<img src="https://img.shields.io/github/issues/GitHamza0206/simba" alt="Issues">
</a>
<a href="https://github.com/GitHamza0206/simba/pulls">
<img src="https://img.shields.io/github/issues-pr/GitHamza0206/simba" alt="Pull Requests">
</a>
<a href="https://pepy.tech/projects/simba-core"><img src="https://static.pepy.tech/badge/simba-core" alt="PyPI Downloads"></a>
</p>

<!-- <a href="https://ibb.co/RHkRGcs"><img src="https://i.ibb.co/ryRDKHz/logo.jpg" alt="logo" border="0"></a> -->
[![Twitter Follow](https://img.shields.io/twitter/follow/zeroualihamza?style=social)](https://x.com/zerou_hamza)

## 📖 Overview

Simba is an open-source, portable Knowledge Management System (KMS) designed specifically for seamless integration with Retrieval-Augmented Generation (RAG) systems. With its intuitive UI, modular architecture, and powerful SDK, Simba simplifies knowledge management, allowing developers to focus on building advanced AI solutions.

# Table of Contents

- [Table of Contents](#table-of-contents)
  - [🚀 Features](#-features)
  - [🎥 Demo](#-demo)
  - [🛠️ Getting Started](#️-getting-started)
    - [📋 Prerequisites](#-prerequisites)
  - [🔌 Quickstart Simba SDK Usage](#-quickstart-simba-sdk-usage)
    - [📦 Installation](#-installation)
    - [🔑 Configuration](#-configuration)
    - [🚀 Running Simba](#-running-simba)
  - [🐳 Docker Deployment](#-docker-deployment)
  - [🏁 Roadmap](#-roadmap)
  - [🤝 Contributing](#-contributing)
  - [💬 Support \& Contact](#-support--contact)

## 🚀 Features

- **🔌 Powerful SDK:** Comprehensive Python SDK for easy integration.
- **🧩 Modular Architecture:** Flexible integration of vector stores, embedding models, chunkers, and parsers.
- **🖥️ Modern UI:** User-friendly interface for managing document chunks.
- **🔗 Seamless Integration:** Effortlessly connects with any RAG-based system.
- **👨‍💻 Developer-Centric:** Simplifies complex knowledge management tasks.
- **📦 Open Source & Extensible:** Community-driven with extensive customization options.

## 🎥 Demo

![Watch the demo](/assets/demo.gif)

## 🛠️ Getting Started

### 📋 Prerequisites

Ensure you have the following installed:

- [Python](https://www.python.org/) 3.11+
- [Poetry](https://python-poetry.org/)
- [Redis](https://redis.io/) 7.0+
- [Node.js](https://nodejs.org/) 20+
- [Git](https://git-scm.com/)
- (Optional) Docker

## 🔌 Quickstart Simba SDK Usage

```bash
pip install simba-client
```

Leverage Simba's SDK for powerful programmatic access:

```python
from simba_sdk import SimbaClient

client = SimbaClient(api_url="http://localhost:8000") # you need to install simba-core and run simba server first 

document = client.documents.create(file_path="path/to/your/document.pdf")
document_id = document[0]["id"]

parsing_result = client.parser.parse_document(document_id, parser="docling", sync=True)

retrieval_results = client.retriever.retrieve(query="your-query")

for result in retrieval_results["documents"]:
    print(f"Content: {result['page_content']}")
    print(f"Metadata: {result['metadata']['source']}")
    print("====" * 10)
```

Explore more in the [Simba SDK documentation](https://github.com/GitHamza0206/simba/tree/main/simba_sdk).

### 📦 Installation

Install Simba core :

```bash
pip install simba-core
```

Or Clone and set up the repository:

```bash
git clone https://github.com/GitHamza0206/simba.git
cd simba
poetry config virtualenvs.in-project true
poetry install
source .venv/bin/activate
```

### 🔑 Configuration

Create a `.env` file:

```bash
OPENAI_API_KEY=your_openai_api_key
REDIS_HOST=localhost
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

Configure `config.yaml`:

```yaml
# config.yaml

project:
  name: "Simba"
  version: "1.0.0"
  api_version: "/api/v1"

paths:
  base_dir: null  # Will be set programmatically
  faiss_index_dir: "vector_stores/faiss_index"
  vector_store_dir: "vector_stores"

llm:
  provider: "ollama"
  model_name: "llama3.2"
  temperature: 0.0
  max_tokens: null
  streaming: true
  additional_params: {}

embedding:
  provider: "ollama"
  model_name: "llama3.2:latest"
  #model_name: "openai/clip-vit-base-patch32"
  device: "mps"  # Changed from mps to cpu for container compatibility
  additional_params: {}

vector_store:
  provider: "faiss"
  collection_name: "simba_collection"

  additional_params: {}

chunking:
  chunk_size: 512
  chunk_overlap: 200

retrieval:
  method: "hybrid" # Options: default, semantic, keyword, hybrid, ensemble, reranked
  k: 5
  # Method-specific parameters
  params:
    # Semantic retrieval parameters
    score_threshold: 0.5
    
    # Hybrid retrieval parameters
    prioritize_semantic: true
    
    # Ensemble retrieval parameters
    weights: [0.7, 0.3]  # Weights for semantic and keyword retrievers
    
    # Reranking parameters
    reranker_model: colbert
    reranker_threshold: 0.7

# Database configuration
database:
  provider: litedb # Options: litedb, sqlite
  additional_params: {}

celery: 
  broker_url: ${CELERY_BROKER_URL:-redis://redis:6379/0}
  result_backend: ${CELERY_RESULT_BACKEND:-redis://redis:6379/1}
```

### 🚀 Running Simba

Start the server, frontend, and parsers:

```bash
simba server
simba front
simba parsers
```

## 🐳 Docker Deployment

Deploy Simba using Docker:

- **CPU:**
```bash
DEVICE=cpu make build
DEVICE=cpu make up
```

- **NVIDIA GPU:**
```bash
DEVICE=cuda make build
DEVICE=cuda make up
```

- **Apple Silicon:**
```bash
DEVICE=cpu make build
DEVICE=cpu make up
```

## 🛠️ No Docker? Run Locally

If you prefer to run Simba directly on your machine without Docker:

1. **Install Requirements:**
   - [Ollama](https://ollama.com/) (Run `ollama serve` and pull models: `ollama pull llama3.2` and `ollama pull llama3.2:latest`)
   - [Redis](https://redis.io/) (Run `redis-server`)
   - [Python](https://www.python.org/) 3.11+
   - [Poetry](https://python-poetry.org/)
   - Node.js 20+

2. **Setup and Check:**
   We provide a script to check your local environment:
   ```bash
   make run-local
   ```
   Or manually:
   ```bash
   chmod +x scripts/setup_local.sh
   ./scripts/setup_local.sh
   ```

3. **Run Services:**
   Open 3 terminal tabs and run:
   ```bash
   # Terminal 1: Backend Server
   poetry run simba server

   # Terminal 2: Parsing Worker
   poetry run simba parsers

   # Terminal 3: Frontend
   poetry run simba front
   ```

## 🏁 Roadmap

- [x] 💻 pip install simba-core
- [x] 🔧 pip install simba-sdk
- [ ] 🌐 www.simba-docs.com
- [ ] 🔒 Auth & access management
- [ ] 🕸️ Web scraping
- [ ] ☁️ Cloud integrations (Azure/AWS/GCP)
- [ ] 📚 Additional parsers and chunkers
- [ ] 🎨 Enhanced UX/UI

## 🤝 Contributing

We welcome contributions! Follow these steps:

- Fork the repository
- Create a feature or bugfix branch
- Commit clearly documented changes
- Submit a pull request

## 💬 Support & Contact

For support or inquiries, open an issue on GitHub or contact [Hamza Zerouali](mailto:zeroualihamza0206@gmail.com).