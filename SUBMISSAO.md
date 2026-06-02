# Fluxo de Submissão

O código da solução fica em `my-solution/` neste repo. O repo do participante
(`marcuspmd/rinha-backend-2026-rust`) é separado e precisa receber os arquivos
atualizados manualmente.

---

## Estrutura dos dois repos

```
rinha-de-backend-2026/          ← repo da competição (este)
└── my-solution/
    ├── api/src/main.rs         ← código Rust
    ├── haproxy/haproxy.cfg     ← config do proxy
    ├── Cargo.toml / Cargo.lock
    ├── index.bin               ← índice IVF (187MB, não vai pro git)
    └── target/
        └── x86_64-unknown-linux-musl/release/api  ← binário compilado

rinha-backend-2026-rust/        ← repo do participante
├── main branch                 ← código fonte
└── submission branch           ← docker-compose.yml + haproxy/ (o que é testado)
```

---

## Passo a passo

### 1. Editar o código

Edite os arquivos em `my-solution/`:
- `api/src/main.rs` — lógica principal
- `haproxy/haproxy.cfg` — configuração do proxy
- `docker-compose.yml` — NPROBE, WORKERS, limites de recurso

---

### 2. Compilar o binário (cross-compilation para linux/amd64)

```bash
RUSTFLAGS="-C target-cpu=x86-64-v3 -C linker=x86_64-linux-musl-gcc" \
  cargo build \
    --manifest-path my-solution/Cargo.toml \
    --target x86_64-unknown-linux-musl \
    --release --bin api
```

O binário fica em:
`my-solution/target/x86_64-unknown-linux-musl/release/api`

> **Não usa QEMU** — compila nativamente no Mac via musl cross-compiler.

---

### 3. Build e push da imagem Docker

```bash
docker buildx build \
  --platform linux/amd64 \
  -t docker.io/marcuspmd/rinha-backend-2026-rust:latest \
  -f Dockerfile.publish \
  . --push
```

O `Dockerfile.publish` usa base `scratch` e copia:
- `my-solution/target/x86_64-unknown-linux-musl/release/api`
- `my-solution/index.bin`
- `resources/mcc_risk.json`

> Execute a partir da **raiz** do repo `rinha-de-backend-2026`.

---

### 4. Preparar o repo do participante

Na primeira vez, clone o repo:

```bash
cd /tmp && gh repo clone marcuspmd/rinha-backend-2026-rust rinha-2026-rust
```

Nas vezes seguintes, apenas atualize:

```bash
cd /tmp/rinha-2026-rust && git fetch --all
```

---

### 5. Atualizar o branch `main` (código fonte)

```bash
# Copiar arquivos alterados
cp my-solution/api/src/main.rs     /tmp/rinha-2026-rust/api/src/main.rs
cp my-solution/haproxy/haproxy.cfg /tmp/rinha-2026-rust/haproxy/haproxy.cfg
cp my-solution/Cargo.toml          /tmp/rinha-2026-rust/Cargo.toml
cp my-solution/Cargo.lock          /tmp/rinha-2026-rust/Cargo.lock

# Commit e push
cd /tmp/rinha-2026-rust
git checkout main
git add -A
git commit -m "descrição das mudanças"
git push origin main
```

---

### 6. Atualizar o branch `submission` (o que a competição testa)

O branch `submission` contém apenas:
- `docker-compose.yml` — referencia a imagem e define NPROBE/WORKERS
- `haproxy/haproxy.cfg` — config do proxy

```bash
cd /tmp/rinha-2026-rust
git checkout submission

# Copiar arquivos do submission
cp my-solution/haproxy/haproxy.cfg /tmp/rinha-2026-rust/haproxy/haproxy.cfg
# Editar docker-compose.yml diretamente se necessário (NPROBE, WORKERS)

git add -A
git commit -m "descrição"
git push origin submission
```

> **Atenção:** O `docker-compose.yml` do submission branch é diferente do
> `my-solution/docker-compose.yml`. Edite diretamente em `/tmp/rinha-2026-rust/docker-compose.yml`
> quando quiser mudar NPROBE ou WORKERS sem rebuild de imagem.

---

### 7. Abrir issue para rodar o teste

```bash
gh issue create \
  --repo zanfranceschi/rinha-de-backend-2026 \
  --title "rinha/test marcuspmd-rust" \
  --body  "rinha/test marcuspmd-rust"
```

A competição roda o `docker-compose.yml` do branch `submission` com a imagem
que está no Docker Hub.

---

## Resumo: o que precisa rebuild vs. o que é só push

| Mudança | Precisa compilar? | Precisa push da imagem? | Precisa push do submission? |
|---------|:-----------------:|:----------------------:|:---------------------------:|
| Código Rust (`main.rs`) | ✅ Sim | ✅ Sim | ❌ Não |
| `haproxy.cfg` | ❌ Não | ❌ Não | ✅ Sim |
| `NPROBE` / `WORKERS` | ❌ Não | ❌ Não | ✅ Sim |
| Ambos | ✅ Sim | ✅ Sim | ✅ Sim |

---

## Referências rápidas

| Item | Valor |
|------|-------|
| Docker Hub image | `docker.io/marcuspmd/rinha-backend-2026-rust:latest` |
| Repo participante | `https://github.com/marcuspmd/rinha-backend-2026-rust` |
| Repo local clone | `/tmp/rinha-2026-rust/` |
| Prazo submissão | 2026-06-05T23:59:59-03:00 |
| NPROBE atual | 64 (estável, E=4) |
| WORKERS atual | 4 |
