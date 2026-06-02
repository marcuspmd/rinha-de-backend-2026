# Guia de Execução e Testes – Rinha de Backend 2026

Este guia detalha como compilar, rodar e validar a solução de detecção de fraudes localmente.

---

## 1. Inicializando a Solução

Para subir os containers do HAProxy e das duas instâncias de API (que compilarão e pré-processarão o índice `index.bin` no primeiro build):

```bash
# Subir a stack inteira compilando do zero
docker compose -f my-solution/docker-compose.yml up --build -d
```

> [!NOTE]
> O primeiro build pode demorar cerca de 1-2 minutos porque o Rust irá compilar o pré-processador e a API, e em seguida rodar o agrupamento de 3 milhões de vetores no K-Means. Os builds seguintes serão instantâneos por conta do cache do Docker.

---

## 2. Monitorando Recursos e Logs

Você pode acompanhar a memória e CPU em tempo real para verificar se eles respeitam os limites estipulados de 350 MB e 1 CPU:

```bash
# Monitorar recursos consumidos
docker stats haproxy api1 api2

# Ver logs das APIs
docker logs -f api1
docker logs -f api2
```

Para verificar se a API está pronta e saudável:
```bash
curl -i http://localhost:9999/ready
```
Deverá retornar `HTTP/1.1 200 OK`.

---

## 3. Executando os Testes de Validação

O repositório oficial da Rinha inclui testes em K6 configurados. Podemos rodá-los usando o Docker local.

### A. Teste de Fumaça (Smoke Test)
Um teste rápido (10 segundos) para validar que as respostas da API estão corretas e não há erros de normalização:

```bash
docker compose -f test/docker-compose.yml --profile smoke up
```

### B. Teste de Carga Total (k6)
Este teste roda o cenário oficial, escalando até **900 requisições por segundo** durante 2 minutos.

Se você possuir o `k6` instalado localmente na sua máquina:
```bash
# Garanta permissão de execução
chmod +x run.sh

# Rodar o teste local
./run.sh
```

Caso não possua o `k6` local, utilize o container oficial via Docker Compose:
```bash
docker compose -f test/docker-compose.yml --profile test up
```

---

## 4. Analisando os Resultados

Após a conclusão do teste de carga total, o arquivo `test/results.json` será gerado. Ele conterá o breakdown de acurácia e pontuação detalhada.

Para inspecionar via terminal (caso possua `jq`):
```bash
cat test/results.json | jq
```

---

## 5. Limpando o Ambiente

Para parar e remover todos os containers do teste e da API:

```bash
# Parar a API e Load Balancer
docker compose -f my-solution/docker-compose.yml down

# Parar o K6 (se rodado via docker)
docker compose -f test/docker-compose.yml down
```
