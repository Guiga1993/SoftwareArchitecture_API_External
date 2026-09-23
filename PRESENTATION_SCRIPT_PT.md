# Roteiro de apresentacao do projeto

Este roteiro separa o que deve ser falado do que deve ser feito durante a
demonstracao.

Os valores prontos para copiar no Swagger, organizados na ordem de execucao,
estao em [SWAGGER_TEST_VALUES_PT.md](SWAGGER_TEST_VALUES_PT.md).

- **FALA:** texto que deve ser pronunciado.
- **ACAO NA TELA:** instrucao de navegacao; nao deve ser pronunciada.
- **NOTA PARA VOCE:** explicacao ou alerta; nao deve ser pronunciado.

> **Duracao prevista:** aproximadamente 8 minutos. As partes 1 a 4 seguem os
> tempos sugeridos. A demonstracao completa da API principal leva de 4 a 6
> minutos porque inclui todas as rotas implementadas.

## 0. Preparacao antes da apresentacao

### Checklist

1. Verifique se o Docker Engine esta em execucao.
2. No diretorio `SoftwareArchitecture_API_External`, crie o arquivo `.env` a
   partir de `.env.example` e configure uma chave Shippo valida.
3. Nunca abra o arquivo `.env` durante a gravacao.
4. Inicie todo o sistema:

   ```powershell
   docker compose up --build -d
   ```

5. Confirme o estado dos tres servicos:

   ```powershell
   docker compose ps
   ```

6. Deixe estas paginas abertas em abas diferentes:
  - API secundaria: `http://localhost:8001`
  - API principal: `http://localhost:5001`
  - Front-end: `http://localhost:8080`
7. Use valores unicos para evitar conflito com dados de ensaios anteriores.
   Este roteiro usa o cliente `Demonstracao PUC` e o gerador `GEN-9090`.
8. Anote os identificadores retornados ao criar o cliente, o gerador e o
   vinculo. Nos exemplos abaixo, eles aparecem como `<CUSTOMER_ID>`,
   `<GENERATOR_ID>` e `<ASSET_ID>`.

**NOTA PARA VOCE:** Docker Compose e a ferramenta que inicia e conecta varios
conteineres a partir de um unico arquivo. Um conteiner e um ambiente isolado que
empacota uma aplicacao e suas dependencias.

**NOTA PARA VOCE:** Swagger e a interface visual gerada a partir da especificacao
OpenAPI. Ela permite conhecer e executar as rotas de uma API pelo navegador.

---

## 1. Objetivo da aplicacao - 20 a 60 segundos

**ACAO NA TELA:** Mostre rapidamente o front-end na pagina inicial.

**FALA:**

> O objetivo deste projeto e centralizar o gerenciamento de clientes e de
> geradores de hidrogenio. A aplicacao permite cadastrar os clientes, registrar
> as caracteristicas tecnicas dos geradores e relacionar cada equipamento ao
> seu cliente. Ela tambem utiliza as medidas armazenadas do gerador para validar
> enderecos e solicitar uma estimativa de frete. Dessa forma, evitamos dados
> dispersos e impedimos que a interface acesse diretamente o servico externo de
> transporte.

**NOTA PARA VOCE:** Centralizar significa manter as operacoes e os dados do
dominio em um sistema controlado, em vez de distribui-los em planilhas ou
aplicacoes sem integracao.

---

## 2. Arquitetura e comunicacao - 30 a 60 segundos

**ACAO NA TELA:** Mostre o diagrama de arquitetura em `OVERALL_ARCHITECTURE.md`.

**FALA:**

> A solucao possui tres componentes implementados. O front-end apresenta os
> formularios ao usuario. Ele se comunica por HTTP somente com a API principal,
> que concentra as regras de negocio e persiste os dados em um banco SQLite.
> Quando uma operacao depende de transporte, a API principal envia JSON para a
> API secundaria. Essa API secundaria funciona como uma camada de integracao e
> e o unico componente autorizado a chamar a API externa da Shippo por HTTPS.
> No Docker, o nginx entrega o front-end e encaminha as requisicoes com o
> prefixo barra API para o back-end. Essa separacao reduz o acoplamento e protege
> a credencial externa.

**NOTA PARA VOCE:**

- API e uma interface que permite a comunicacao entre sistemas por contratos
  definidos.
- HTTP e o protocolo usado nas comunicacoes web. HTTPS e sua versao protegida
  por criptografia.
- JSON e um formato textual estruturado para troca de dados.
- SQLite e um banco de dados relacional armazenado em um arquivo local.
- nginx e o servidor que entrega os arquivos do front-end e atua como proxy
  reverso. Proxy reverso e um intermediario que recebe a requisicao e a
  encaminha ao servico interno correto.
- Acoplamento e o nivel de dependencia entre componentes. Menor acoplamento
  facilita manutencao e substituicao de uma integracao.
- Persistencia e a conservacao dos dados mesmo depois que o processo termina.

---

## 3. API externa: Shippo - 30 a 60 segundos

**ACAO NA TELA:** Mantenha o diagrama visivel e destaque a Shippo no extremo do
fluxo.

**FALA:**

> A API externa utilizada e a Shippo, um servico de terceiros para operacoes de
> transporte. Neste projeto, ela valida enderecos dos Estados Unidos e consulta
> opcoes de frete fornecidas por transportadoras. A credencial da Shippo existe
> somente na API secundaria e e carregada por variavel de ambiente. Assim, ela
> nao aparece no navegador nem na API principal. Como esse servico esta fora do
> nosso controle, a aplicacao tambem trata situacoes como endereco invalido,
> ausencia de tarifas, indisponibilidade e tempo limite de comunicacao. 
> Abra https://docs.goshippo.com/

**NOTA PARA VOCE:**

- Servico de terceiros e uma aplicacao mantida por outra organizacao.
- Variavel de ambiente e uma configuracao fornecida ao processo sem grava-la no
  codigo-fonte.
- Tempo limite, ou timeout, e o periodo maximo de espera por uma resposta.
- A Shippo pode consultar APIs de transportadoras. Essa e uma dependencia
  indireta; o projeto nao chama as transportadoras diretamente.

---

## 4. Segundo componente: API secundaria - 60 a 90 segundos

**ACAO NA TELA:** Abra `http://localhost:8001`. Mostre que `GET /` redireciona o
navegador para `/openapi`. No Swagger, expanda cada rota, clique em **Try it
out** e depois em **Execute**.

**FALA:**

> Ao acessar a rota raiz, a API me redireciona para sua documentacao interativa,
> onde posso conhecer e testar os contratos disponiveis.

### 4.1 Verificacao de saude

**ACAO NA TELA:** Execute `GET /health`.

**FALA:**

> Esta e a API secundaria, responsavel por isolar a integracao. Primeiro,
> verifico sua rota de saude. A resposta informa que o processo esta ativo, mas
> nao realiza uma chamada a Shippo.

Resposta esperada:

```json
{
  "status": "up",
  "service": "shippo-integration"
}
```

### 4.2 Validacao de endereco

**ACAO NA TELA:** Execute `POST /validate-address` com o JSON abaixo.

```json
{
  "customer_name": "PUC Demonstration",
  "street1": "215 Clayton Street",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94117",
  "country": "US"
}
```

**FALA:**

> Nesta rota, envio um endereco em JSON. A API valida o formato, chama a Shippo
> e devolve um resultado normalizado, informando se o endereco foi considerado
> valido.

### 4.3 Cotacao direta

**ACAO NA TELA:** Execute `POST /shipping-quote` com o JSON abaixo.

```json
{
  "address_from": {
    "name": "PUC Demonstration",
    "street1": "215 Clayton Street",
    "city": "San Francisco",
    "state": "CA",
    "zip": "94117",
    "country": "US"
  },
  "address_to": {
    "name": "Destination Company",
    "street1": "20 West 34th Street",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "US"
  },
  "parcels": [
    {
      "length": "24",
      "width": "16",
      "height": "12",
      "distance_unit": "in",
      "weight": "50",
      "mass_unit": "lb"
    }
  ]
}
```

**FALA:**

> Por fim, envio origem, destino e dados do pacote. A API consulta a Shippo e
> seleciona a tarifa disponivel de menor valor. Transportadora, servico, preco e
> prazo podem variar porque sao dados externos obtidos em tempo real.

**NOTA PARA VOCE:** Endpoint e o endereco de uma operacao da API. Payload e o
conjunto de dados enviado no corpo da requisicao. Normalizar e transformar uma
resposta externa em um formato estavel usado pelo projeto.

---

## 5. Componente principal: API back-end - 4 a 6 minutos

**ACAO NA TELA:** Abra `http://localhost:5001`. Mostre que `GET /` tambem
redireciona para `/openapi`. Explique que os campos de cliente, gerador e vinculo
aparecem como formulario no Swagger. Execute as rotas na ordem abaixo. Nao use
IDs fixos: copie os IDs efetivamente retornados.

**FALA DE ABERTURA:**

> Esta e a API principal. Ela implementa as regras do sistema, gerencia a base
> SQLite e coordena as chamadas para a API secundaria. Agora vou demonstrar
> todas as rotas implementadas. A rota raiz me trouxe ate esta documentacao
> interativa.

### 5.1 Saude da API principal

**ACAO NA TELA:** Execute `GET /health`.

**FALA:**

> A rota de saude confirma que o processo principal esta ativo.

Resposta esperada:

```json
{
  "status": "up",
  "service": "backend"
}
```

### 5.2 CRUD de clientes

**NOTA PARA VOCE:** CRUD significa criar, consultar, atualizar e excluir. A sigla
vem de Create, Read, Update e Delete.

#### Criar

**ACAO NA TELA:** Execute `POST /customer` preenchendo os campos do formulario:

| Campo | Valor |
|---|---|
| `name` | `Demonstracao PUC` |
| `email` | `demonstracao.puc.9090@example.com` |
| `tx_id` | `909-09-9090` |

**FALA:**

> Primeiro, cadastro um cliente. A API valida o nome, o e-mail e o identificador
> fiscal antes de persistir o registro.

**ACAO NA TELA:** Anote o `customer_id` retornado como `<CUSTOMER_ID>`.

#### Listar e consultar

**ACAO NA TELA:** Execute `GET /customers`. Depois execute `GET /customer` com
`customer_id = <CUSTOMER_ID>`.

**FALA:**

> A rota no plural lista a colecao de clientes. A rota no singular recebe o
> identificador e retorna apenas o cliente selecionado.

#### Atualizar

**ACAO NA TELA:** Execute `PUT /customer` com
`customer_id = <CUSTOMER_ID>` e estes campos:

| Campo | Valor |
|---|---|
| `name` | `Demonstracao PUC Atualizada` |
| `email` | `demonstracao.puc.9090@example.com` |
| `tx_id` | `909-09-9090` |

**FALA:**

> Com o metodo PUT, atualizo os dados do mesmo cliente sem alterar sua
> identidade no banco.

### 5.3 CRUD de geradores de hidrogenio

#### Criar

**ACAO NA TELA:** Execute `POST /hydrogen-generator` com os campos:

| Campo | Valor |
|---|---:|
| `serial_number` | `GEN-9090` |
| `acquisition_type` | `Leasing` |
| `stack_type` | `PEMFC` |
| `number_of_cells` | `100` |
| `stack_voltage` | `48.5` |
| `current_density` | `1.2` |
| `length_in` | `24` |
| `width_in` | `16` |
| `height_in` | `12` |
| `weight_lb` | `50` |

**FALA:**

> Agora cadastro um gerador com seus dados comerciais, eletricos e fisicos. As
> dimensoes e o peso tambem sao validados porque serao usados posteriormente na
> cotacao de frete.

**ACAO NA TELA:** Anote o `generator_id` retornado como `<GENERATOR_ID>`.

#### Listar e consultar

**ACAO NA TELA:** Execute `GET /hydrogen-generators`. Depois execute
`GET /hydrogen-generator` com `serial_number = GEN-9090`.

**FALA:**

> Assim como nos clientes, posso listar todos os geradores ou consultar um
> equipamento especifico pelo numero de serie.

#### Atualizar

**ACAO NA TELA:** Execute `PUT /hydrogen-generator` com o parametro de consulta
`serial_number = GEN-9090` e os campos:

| Campo | Valor |
|---|---:|
| `serial_number` | `GEN-9090` |
| `acquisition_type` | `Direct Sales` |
| `stack_type` | `PEMFC` |
| `number_of_cells` | `110` |
| `stack_voltage` | `50` |
| `current_density` | `1.3` |
| `length_in` | `24` |
| `width_in` | `16` |
| `height_in` | `12` |
| `weight_lb` | `50` |

**FALA:**

> Aqui altero o tipo de aquisicao e alguns dados tecnicos, mantendo o numero de
> serie usado para localizar o registro.

### 5.4 CRUD do vinculo entre cliente e gerador

#### Criar

**ACAO NA TELA:** Execute `POST /asset` com os campos abaixo. Use os IDs reais
obtidos anteriormente.

| Campo | Valor |
|---|---|
| `customer_id` | `<CUSTOMER_ID>` |
| `generator_id` | `<GENERATOR_ID>` |
| `generator_qtd` | `2` |
| `installation_date` | `2026-09-22T10:00:00` |

**FALA:**

> Esta operacao cria o vinculo entre o cliente e o modelo de gerador. A API
> verifica se os dois registros existem e armazena quantidade e data de
> instalacao.

**ACAO NA TELA:** Anote o `asset_id` retornado como `<ASSET_ID>`.

#### Listar e consultar

**ACAO NA TELA:** Execute `GET /assets`. Depois execute `GET /asset` com
`asset_id = <ASSET_ID>`.

**FALA:**

> Estas rotas listam todos os vinculos e consultam individualmente o vinculo que
> acabei de criar.

#### Atualizar

**ACAO NA TELA:** Execute `PUT /asset` com `asset_id = <ASSET_ID>` e:

| Campo | Valor |
|---|---|
| `customer_id` | `<CUSTOMER_ID>` |
| `generator_id` | `<GENERATOR_ID>` |
| `generator_qtd` | `3` |
| `installation_date` | `2026-09-22T10:00:00` |

**FALA:**

> Atualizo a quantidade relacionada ao cliente de duas para tres unidades.

### 5.5 Validacao de endereco pela API principal

**ACAO NA TELA:** Execute `POST /validate-address` com:

```json
{
  "customer_name": "Demonstracao PUC",
  "street1": "215 Clayton Street",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94117"
}
```

**FALA:**

> A API principal valida o contrato de entrada e delega a verificacao do
> endereco para a API secundaria. O identificador de correlacao permite
> acompanhar a mesma requisicao entre os dois servicos.

**NOTA PARA VOCE:** Identificador de correlacao e um valor unico propagado entre
servicos para localizar nos logs todas as etapas da mesma requisicao.

### 5.6 Cotacao pela API principal

**ACAO NA TELA:** Execute `POST /shipping-quote`, substituindo
`<GENERATOR_ID>` pelo valor real:

```json
{
  "origin_name": "Demonstracao PUC",
  "origin_street": "215 Clayton Street",
  "origin_city": "San Francisco",
  "origin_state": "CA",
  "origin_zip": "94117",
  "customer_name": "Destination Company",
  "destination_street": "20 West 34th Street",
  "destination_city": "New York",
  "destination_state": "NY",
  "destination_zip": "10001",
  "generator_id": <GENERATOR_ID>,
  "generator_quantity": 1
}
```

**FALA:**

> Nesta cotacao, o usuario informa os enderecos, o identificador do gerador e a
> quantidade. A API principal busca no banco as dimensoes e o peso confiaveis do
> equipamento, monta um pacote por unidade e envia o pedido para a API
> secundaria. Portanto, o cliente nao pode adulterar as medidas na requisicao de
> cotacao.

### 5.7 Exclusao e limpeza dos dados

**ACAO NA TELA:** Execute exatamente nesta ordem:

1. `DELETE /asset` com `asset_id = <ASSET_ID>`.
2. `DELETE /hydrogen-generator` com `serial_number = GEN-9090`.
3. `DELETE /customer` com `customer_id = <CUSTOMER_ID>`.

**FALA:**

> Para concluir o ciclo CRUD, removo primeiro o vinculo e depois os registros de
> gerador e cliente. Essa ordem respeita as dependencias entre os dados e deixa
> o ambiente limpo para uma nova demonstracao.

**FALA DE ENCERRAMENTO DA API PRINCIPAL:**

> Com isso, foram demonstradas todas as rotas da API principal: saude, cadastro,
> consulta, atualizacao, exclusao, validacao de endereco e cotacao de frete.

---

## 6. Demonstracao complementar do front-end - 30 a 45 segundos

**ACAO NA TELA:** Abra `http://localhost:8080`. Mostre as quatro abas: clientes,
geradores, vinculos e cotacao. Pressione `F12`, abra a guia **Network** e execute
uma listagem, como **List All Customers**.

**FALA:**

> Como complemento, este e o front-end executado pelo nginx. Ele oferece as
> mesmas operacoes por formularios organizados em quatro areas. Ao listar os
> clientes, a guia de rede mostra uma requisicao com o prefixo barra API. O nginx
> remove esse prefixo e encaminha a chamada para a API principal. O navegador
> nunca acessa diretamente a API secundaria nem a Shippo, o que preserva os
> limites da arquitetura e mantem a credencial fora da interface.

**NOTA PARA VOCE:** A guia Network, ou Rede, mostra as requisicoes HTTP feitas
pelo navegador. Se os dados foram excluidos na etapa anterior, a lista vazia e
uma resposta valida. Para mostrar uma linha, faca esta etapa antes das exclusoes.

---

## 7. Encerramento - 15 a 25 segundos

**FALA:**

> Em resumo, a solucao separa interface, regras de negocio e integracao externa.
> A API principal controla os dados e as validacoes do dominio, enquanto a API
> secundaria protege a dependencia da Shippo. Os conteineres tornam a execucao
> reproduzivel, o SQLite preserva os registros e os identificadores de
> correlacao ajudam a rastrear as chamadas entre os servicos.

---

## 8. Plano de contingencia

Use estas explicacoes somente se ocorrer um problema durante a apresentacao.

### Chave Shippo ausente ou invalida

**FALA:**

> A API secundaria esta ativa, mas a operacao externa foi recusada porque a
> credencial da Shippo nao esta configurada ou nao e valida. A separacao permite
> identificar a falha sem afetar as operacoes locais de cadastro.

### Shippo indisponivel ou timeout

**FALA:**

> A API local recebeu a requisicao corretamente, mas o provedor externo nao
> respondeu dentro do tempo esperado. O sistema converte essa falha em um status
> HTTP controlado, em vez de expor detalhes internos.

### Nenhuma tarifa disponivel

**FALA:**

> A comunicacao foi concluida, mas nenhuma transportadora ofereceu uma tarifa
> para este envio. Isso e um resultado de negocio valido, identificado pelo
> codigo `NO_RATES`, e nao uma falha do processo local.

### Endereco invalido

**FALA:**

> A Shippo recebeu o endereco, mas nao conseguiu confirma-lo. A API secundaria
> normaliza esse resultado para que a API principal e a interface tratem a
> situacao de forma consistente.

### Conflito ao criar dados

**ACAO NA TELA:** Troque `GEN-9090`, o e-mail e o Tax ID por valores ainda nao
utilizados, ou execute as rotas de exclusao para remover os dados do ensaio.

**NOTA PARA VOCE:**

- Status HTTP e o numero que resume o resultado da requisicao. Por exemplo, 200
  indica processamento aceito, 422 indica entrada invalida e codigos 5xx
  indicam falhas no servidor ou em uma dependencia.
- Token ou chave de API e uma credencial usada para autenticar o sistema perante
  um servico externo. Ela nunca deve aparecer no video, Swagger ou codigo.
- Gunicorn e o servidor que executa as aplicacoes Flask dentro dos conteineres.

---

## 9. Conferencia final de cobertura

### API secundaria

- [ ] `GET /` com redirecionamento para `/openapi`
- [ ] `GET /health`
- [ ] `POST /validate-address`
- [ ] `POST /shipping-quote`

### API principal

- [ ] `GET /` com redirecionamento para `/openapi`
- [ ] `GET /health`
- [ ] `POST /customer`
- [ ] `GET /customers`
- [ ] `GET /customer`
- [ ] `PUT /customer`
- [ ] `POST /hydrogen-generator`
- [ ] `GET /hydrogen-generators`
- [ ] `GET /hydrogen-generator`
- [ ] `PUT /hydrogen-generator`
- [ ] `POST /asset`
- [ ] `GET /assets`
- [ ] `GET /asset`
- [ ] `PUT /asset`
- [ ] `POST /validate-address`
- [ ] `POST /shipping-quote`
- [ ] `DELETE /asset`
- [ ] `DELETE /hydrogen-generator`
- [ ] `DELETE /customer`
