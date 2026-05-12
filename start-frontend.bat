@echo off
cd frontend
if not exist node_modules (
  pnpm install
)
pnpm dev -- --open
