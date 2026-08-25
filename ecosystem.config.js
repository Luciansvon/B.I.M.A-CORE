const agentMemoryApps = process.env.AGENTMEMORY_ENABLED === "true" ? [
  {
    name: "agentmemory",
    script: "node_modules/.bin/agentmemory",
    args: "--tools core",
    interpreter: "none",
    cwd: "/home/bima_lucian/BIMA_CORE/services/agentmemory",
    watch: false,
    env: {
      NODE_ENV: "production",
      PATH: "/home/bima_lucian/.local/bin:/usr/local/bin:/usr/bin:/bin",
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
      interpreter: "/home/bima_lucian/BIMA_CORE/bima_env/bin/python3",
      cwd: "/home/bima_lucian/BIMA_CORE",
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
        EMBEDDING_MODEL_ARSIP: "qwen/qwen3-embedding-8b",
        EMBEDDING_DIM_ARSIP: "1024",
        EMBED_BATCH_SIZE: "64",
        // Hybrid vector + BM25 tetap aktif; CrossEncoder lokal dimatikan.
        RERANKER_ENABLED: "false",
        // STT large-v3-turbo (akurasi ID jauh > small), CPU int8 biar aman VRAM 4GB
        STT_MODEL_SIZE: "/home/bima_lucian/models/faster-whisper-large-v3-turbo",
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
      args: "tunnel --config /dev/null --protocol http2 --url http://127.0.0.1:8000",
      cwd: "/home/bima_lucian/BIMA_CORE",
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "./logs/tunnel-error.log",
      out_file: "./logs/tunnel-output.log",
      merge_logs: true,
      autorestart: true,
      restart_delay: 3000,
    },
    {
      name: "bima-whatsapp",
      script: "index.js",
      cwd: "/home/bima_lucian/BIMA_CORE/whatsapp",
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
      interpreter: "/home/bima_lucian/BIMA_CORE/bima_env/bin/python3",
      cwd: "/home/bima_lucian/BIMA_CORE",
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
