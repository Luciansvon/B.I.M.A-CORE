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
        // RAG reranker multilingual (bge-reranker-v2-m3) — path lokal biar ga re-download flaky
        RERANKER_MODEL: "/home/bima_lucian/models/bge-reranker-v2-m3",
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
      max_memory_restart: "3G",          // Auto restart kalau RAM bocor
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
