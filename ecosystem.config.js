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
      args: "tunnel --protocol http2 --url http://localhost:8000",
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
    }
  ]
};
