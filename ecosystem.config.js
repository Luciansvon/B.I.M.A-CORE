const path = require("path");

const PROJECT_ROOT = __dirname;
const PYTHON_PATH = process.platform === "win32"
  ? path.join(PROJECT_ROOT, "bima_env", "Scripts", "python.exe")
  : path.join(PROJECT_ROOT, "bima_env", "bin", "python3");
const NULL_DEVICE = process.platform === "win32" ? "NUL" : "/dev/null";

const agentMemoryApps = process.env.AGENTMEMORY_ENABLED === "true" ? [
  {
    name: "agentmemory",
    script: "node_modules/.bin/agentmemory",
    args: "--tools core",
    interpreter: "none",
    cwd: path.join(PROJECT_ROOT, "services", "agentmemory"),
    watch: false,
    env: {
      NODE_ENV: "production",
      PATH: process.env.PATH,
    },
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "../../logs/agentmemory-error.log",
    out_file: "../../logs/agentmemory-output.log",
    merge_logs: true,
    autorestart: true,
    max_memory_restart: "1G",
    restart_delay: 5000,
    exp_backoff_restart_delay: 2000,
  },
] : [];

module.exports = {
  apps : [
    {
      name: "anisa-v3",
      script: "main.py",
      interpreter: PYTHON_PATH,
      cwd: PROJECT_ROOT,
      watch: false,
      env: {
        NODE_ENV: "production",
        // VPS memory optimization
        TOKENIZERS_PARALLELISM: "false",
        OMP_NUM_THREADS: "2",
        MKL_NUM_THREADS: "2",
        // Daily runtime tidak memakai text-to-speech; STT tetap aktif.
        ENABLE_TTS: "false",
        // Arsip pakai embedding cloud agar model 8B tidak tinggal di RAM WSL.
        EMBEDDING_BACKEND_ARSIP: "cloud",
        EMBEDDING_MODEL_ARSIP: "openrouter/qwen/qwen3-embedding-8b",
        EMBEDDING_DIM_ARSIP: "1024",
        EMBED_BATCH_SIZE: "64",
        // Hybrid vector + BM25 tetap aktif; CrossEncoder lokal dimatikan.
        RERANKER_ENABLED: "false",
        // STT large-v3-turbo (akurasi ID jauh > small), CPU int8 biar aman VRAM 4GB
        STT_MODEL_SIZE: process.env.STT_MODEL_SIZE || "faster-whisper-large-v3-turbo",
        STT_COMPUTE_TYPE: "int8",
        STT_DEVICE: "cpu",
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/error.log",
      out_file: "./logs/output.log",
      merge_logs: true,
      autorestart: true,
      max_memory_restart: "2G",          // Guardrail target RAM Anisa 1-2 GB
      restart_delay: 5000,               // Tunggu 5 detik sebelum restart
      exp_backoff_restart_delay: 1000,   // Exponential backoff kalau crash loop
    },
    {
      name: "bima-tunnel",
      script: "cloudflared",
      args: `tunnel --config ${NULL_DEVICE} --protocol http2 --url http://127.0.0.1:8000`,
      cwd: PROJECT_ROOT,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/tunnel-error.log",
      out_file: "./logs/tunnel-output.log",
      merge_logs: true,
      autorestart: true,
      restart_delay: 3000,
    },
    {
      name: "9router-tunnel",
      script: "cloudflared",
      args: `tunnel run --protocol http2 --url http://127.0.0.1:20128 bima-untuk-anisa`,
      cwd: PROJECT_ROOT,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/9router-tunnel-error.log",
      out_file: "./logs/9router-tunnel-output.log",
      merge_logs: true,
      autorestart: true,
      restart_delay: 3000,
    },
    {
      name: "bima-whatsapp",
      script: "index.js",
      cwd: path.join(PROJECT_ROOT, "whatsapp"),
      watch: false,
      node_args: "--max-old-space-size=512",
      env: {
        NODE_ENV: "production",
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "../logs/wa-error.log",
      out_file: "../logs/wa-output.log",
      merge_logs: true,
      autorestart: true,
      max_memory_restart: "1G",
      restart_delay: 5000,
      exp_backoff_restart_delay: 2000,
    },
    ...agentMemoryApps,
    {
      name: "anisa-status",
      script: "scripts/status_collector.py",
      interpreter: PYTHON_PATH,
      cwd: PROJECT_ROOT,
      watch: false,
      autorestart: true,
      restart_delay: 5000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/status-error.log",
      out_file: "./logs/status-output.log",
      merge_logs: true,
    }
  ]
};
