# Diretrizes e Arquitetura Rinha de Backend 2026 - Gemini

Este arquivo serve como contexto inicial e diretrizes de desenvolvimento para o **Gemini** (e outros assistentes de IA) no projeto da **Rinha de Backend 2026 - Fraud Detection**. O foco absoluto é **performance máxima** sob as restrições estritas de recursos (1 CPU e 350 MB RAM totais).

---

## 1. Stack Tecnológica

- **Linguagem:** Rust (compilação nativa, sem garbage collector, concorrência segura, controle de baixo nível).
- **Servidor HTTP:** [Axum](https://github.com/tokio-rs/axum) + [Tokio](https://github.com/tokio-rs/tokio) rodando em modo **single-thread** por instância da API para evitar overhead de trocas de contexto.
- **Load Balancer:** [HAProxy](http://www.haproxy.org/) (extremamente leve e focado em baixa latência e vazão de conexões na porta `9999`).
- **Algoritmo de Busca Vetorial:** **IVF-Flat (Inverted File Index / K-Means Clustering)**.
- **Carregamento de Dados:** Pré-processamento na etapa de build do Docker, gerando um arquivo binário customizado que as instâncias da API mapeiam diretamente via `mmap` (read-only).

---

## 2. Layout de Memória do Arquivo Binário (IVF Index)

Para garantir alinhamento SIMD ideal (AVX2/SSE) e evitar overhead de parsing no startup das instâncias, geramos um arquivo binário estruturado.

### Estrutura do Arquivo (`index.bin`):
1. **Header (16 bytes):**
   - `magic`: `[u8; 4]` (`b"IVFF"`)
   - `k_clusters`: `u32` (número total de clusters $K$, ex: 512 ou 1024)
   - `n_vectors`: `u32` (número total de vetores $N = 3.000.000$)
   - `padding`: `u4` (alinhamento de 16 bytes)

2. **Centroids ($K \times 64$ bytes):**
   - Array de centroides. Cada centroide possui 14 dimensões float, mas é **preenchido (padded) para 16 floats (`[f32; 16]`)** para alinhar exatamente com as linhas de cache de 64 bytes e possibilitar cargas AVX2 perfeitas.

3. **Cluster Metadata ($K \times 8$ bytes):**
   - Array contendo o `offset` (índice inicial na lista de vetores) e a `quantidade` de vetores pertencentes a cada cluster:
     - `offset`: `u32`
     - `count`: `u32`

4. **Vetor de Features ($N \times 64$ bytes):**
   - Array contíguo com os vetores do dataset agrupados por cluster.
   - Cada vetor de 14 dimensões é armazenado como `[f32; 16]` (64 bytes, preenchendo as duas últimas dimensões com `0.0` ou valor irrelevante para a distância).

5. **Labels ($N \times 1$ byte):**
   - Array contíguo de `u8` com os rótulos de cada vetor na mesma ordem do vetor de features:
     - `0` = `legit`
     - `1` = `fraud`

---

## 3. Otimizações de Performance Críticas

Ao implementar o código Rust, siga estas diretrizes à risca:

### A. Parser de Data ISO-8601 manual
Não utilize a biblioteca `chrono` ou similar para parsing do campo `requested_at` (ex: `"2026-03-11T18:45:53Z"`). Faça o parsing manual fatiando a string diretamente:
- **Hora do dia (UTC):** Extraia os caracteres na posição do índice `11..13` e converta para `f32`.
- **Dia da semana (UTC):** Extraia ano, mês e dia, e utilize o **algoritmo de Sakamoto** para calcular o dia da semana (0 = Segunda, 6 = Domingo) em pouquíssimos ciclos de CPU.

```rust
// Exemplo de algoritmo de Sakamoto para dia da semana (0-6)
fn day_of_week(y: i32, m: i32, d: i32) -> i32 {
    let t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
    let mut y = y;
    if m < 3 {
        y -= 1;
    }
    // Sakamoto retorna 0 para Domingo, 1 para Segunda, etc.
    // Ajustamos para Segunda = 0, Domingo = 6 conforme a regra.
    let sakamoto = (y + y / 4 - y / 100 + y / 400 + t[(m - 1) as usize] + d) % 7;
    (sakamoto + 6) % 7
}
```

### B. Tabela de Risco MCC O(1)
Não use `HashMap` para busca de risco do MCC (`mcc_risk.json`).
- Aloque um array estático de tamanho `10000` de `f32` (ex: `[f32; 10000]`), pré-inicializado com `0.5`.
- No startup da API, popule os MCCs conhecidos do arquivo `mcc_risk.json` convertendo a chave string em índice numérico (ex: `"5411"` $\rightarrow$ `5411`).
- A busca do risco será uma indexação direta de array de custo $O(1)$ sem hash ou ponteiros.

### C. Busca de Conhecidos (Known Merchants)
Os arrays de `known_merchants` no payload do cliente são tipicamente muito curtos (2 a 5 elementos).
- Não converta este array para um `HashSet`.
- Faça uma busca linear simples (`.iter().any(|m| m == merchant_id)`) que aproveita o cache L1 do processador de forma muito mais eficiente e evita alocações.

### D. Computação SIMD para Distância Euclidiana
- Normalize a transação recebida gerando um query vector `[f32; 16]`.
- Encontre os $C$ clusters mais próximos comparando o query vector com os $K$ centroides.
- Varra os vetores dos $C$ clusters selecionados calculando a distância euclidiana quadrática contra o query vector.
- Garanta que o loop de distância seja amigável para auto-vetorização (compiler auto-vectorization) ou utilize intrinsics do Rust/AVX2:
  ```rust
  // Dica para auto-vetorização: processar pedaços contíguos de 16 floats
  // O compilador otimiza isso usando instruções fma (Fused Multiply-Add) se compilado com target-cpu=native.
  ```

---

## 4. Estratégia de Build e Implantação

1. **Script Pré-Processador (`pre-processor`):**
   - Lê os arquivos `resources/references.json.gz`, `resources/normalization.json` e `resources/mcc_risk.json`.
   - Executa o algoritmo K-Means para agrupar os 3.000.000 vetores em $K$ clusters.
   - Gera o arquivo `index.bin` com a estrutura otimizada.
2. **Dockerfile Multi-Stage:**
   - **Stage 1 (Builder & Pre-processor):** Compila o gerador de índice e executa-o para gerar o arquivo `index.bin`. Compila a API Rust em modo Release com `RUSTFLAGS="-C target-cpu=native"`.
   - **Stage 2 (Runtime):** Copia apenas o binário da API Rust e o arquivo `index.bin`.
3. **Docker Compose:**
   - Distribui os limites (ex: HAProxy com `cpus: "0.1"`, e cada instância da API Rust com `cpus: "0.45"`, totalizando `1.0` CPU e respeitando o limite máximo de 350 MB RAM total).

---

## 5. Como o Gemini deve agir

Ao auxiliar o desenvolvedor neste repositório:
1. **Preserve a simplicidade:** Evite criar abstrações desnecessárias que adicionem alocações dinâmicas no caminho crítico das requisições do `/fraud-score`.
2. **Código Zero-Allocation:** Tente reutilizar buffers ou evitar alocações de Heap na rota de POST.
3. **Validação e Ajustes:** Use o pipeline de testes local (`run.sh`) e verifique se o P99 está abaixo de 1-2 ms e a acurácia se aproxima de 100% calibrando os parâmetros $K$ e $C$.
