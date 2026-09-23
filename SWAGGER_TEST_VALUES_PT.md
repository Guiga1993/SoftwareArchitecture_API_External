# Valores prontos para testar todas as rotas no Swagger

Use esta folha durante o teste para evitar digitar os dados. Execute as rotas
na ordem apresentada.

## Antes de comecar

- API secundaria: `http://localhost:8001`
- API principal: `http://localhost:5001`
- Em cada operacao, clique em **Try it out**, informe ou cole os valores e
  clique em **Execute**.
- Os corpos JSON podem ser copiados por inteiro.
- Cliente, gerador e vinculo usam campos separados no Swagger. Copie o valor da
  tabela correspondente para cada campo.
- Anote os IDs retornados nas criacoes. O registro `A` sera excluido durante o
  teste; o registro `B` continuara disponivel para as etapas seguintes:

```text
CUSTOMER_ID_A =
CUSTOMER_ID_B =
GENERATOR_ID_A =
GENERATOR_ID_B =
ASSET_ID_A =
ASSET_ID_B =
```

> Os IDs sao criados pelo banco e nao podem ser previstos. Sempre use os valores
> realmente retornados, mesmo que os exemplos do Swagger mostrem `1`.

---

## Parte A - API secundaria, porta 8001

### A1. `GET /`

Abra `http://localhost:8001`. Nao ha valor para preencher. O navegador deve ser
redirecionado para `/openapi`.

### A2. `GET /health`

Nao ha valor para preencher. Clique em **Try it out** e **Execute**.

### A3. `POST /validate-address` - validar origem

Cole o corpo completo:

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

### A4. `POST /validate-address` - validar destino

Cole o corpo completo:

```json
{
  "customer_name": "Destination Company",
  "street1": "20 West 34th Street",
  "city": "New York",
  "state": "NY",
  "zip_code": "10001",
  "country": "US"
}
```

Confirme que a resposta foi processada antes de solicitar a cotacao. Um
endereco pode ser bem formado e ainda assim nao ser confirmado pela Shippo.

### A5. `POST /shipping-quote`

Cole o corpo completo:

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

---

## Parte B - API principal, porta 5001

### B1. `GET /`

Abra `http://localhost:5001`. Nao ha valor para preencher. O navegador deve ser
redirecionado para `/openapi`.

### B2. `GET /health`

Nao ha valor para preencher. Clique em **Try it out** e **Execute**.

## Cliente

### B3. `POST /customer` - criar cliente A

Copie cada valor para o campo de mesmo nome:

| Campo | Valor para copiar |
|---|---|
| `name` | `Demonstracao Swagger 9080` |
| `email` | `demonstracao.swagger.9080@example.com` |
| `tx_id` | `908-08-9080` |

Anote o `customer_id` da resposta como `CUSTOMER_ID_A`.

### B4. `POST /customer` - criar cliente B

| Campo | Valor para copiar |
|---|---|
| `name` | `Demonstracao Swagger 9090` |
| `email` | `demonstracao.swagger.9090@example.com` |
| `tx_id` | `909-09-9090` |

Anote o `customer_id` da resposta como `CUSTOMER_ID_B`.

### B5. `PUT /customer` - atualizar cliente B

| Campo | Valor para copiar |
|---|---|
| `customer_id` | valor anotado em `CUSTOMER_ID_B` |
| `name` | `Demonstracao Swagger 9090 Atualizada` |
| `email` | `demonstracao.swagger.9090@example.com` |
| `tx_id` | `909-09-9090` |

### B6. `GET /customers` - listar os dois clientes

Nao ha valor para preencher. A resposta deve incluir os clientes `A` e `B`.

### B7. `GET /customer` - consultar cliente B por ID

| Campo | Valor para copiar |
|---|---|
| `customer_id` | valor anotado em `CUSTOMER_ID_B` |

### B8. `DELETE /customer` - excluir cliente A

| Campo | Valor para copiar |
|---|---|
| `customer_id` | valor anotado em `CUSTOMER_ID_A` |

## Gerador

### B9. `POST /hydrogen-generator` - criar gerador A

| Campo | Valor para copiar |
|---|---|
| `serial_number` | `GEN-9080` |
| `acquisition_type` | `Renting` |
| `stack_type` | `Alcaline` |
| `number_of_cells` | `80` |
| `stack_voltage` | `40` |
| `current_density` | `1.0` |
| `length_in` | `20` |
| `width_in` | `14` |
| `height_in` | `10` |
| `weight_lb` | `40` |

Anote o `generator_id` da resposta como `GENERATOR_ID_A`.

### B10. `POST /hydrogen-generator` - criar gerador B

| Campo | Valor para copiar |
|---|---|
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

Anote o `generator_id` da resposta como `GENERATOR_ID_B`.

### B11. `PUT /hydrogen-generator` - atualizar gerador B

O primeiro `serial_number` e o parametro usado para localizar o registro. O
segundo aparece no formulario e representa o valor que sera salvo. Use
`GEN-9090` nos dois.

| Local | Campo | Valor para copiar |
|---|---|---|
| Query | `serial_number` | `GEN-9090` |
| Formulario | `serial_number` | `GEN-9090` |
| Formulario | `acquisition_type` | `Direct Sales` |
| Formulario | `stack_type` | `PEMFC` |
| Formulario | `number_of_cells` | `110` |
| Formulario | `stack_voltage` | `50` |
| Formulario | `current_density` | `1.3` |
| Formulario | `length_in` | `24` |
| Formulario | `width_in` | `16` |
| Formulario | `height_in` | `12` |
| Formulario | `weight_lb` | `50` |

### B12. `GET /hydrogen-generators` - listar os dois geradores

Nao ha valor para preencher. A resposta deve incluir `GEN-9080` e `GEN-9090`.

### B13. `GET /hydrogen-generator` - consultar gerador B

| Campo | Valor para copiar |
|---|---|
| `serial_number` | `GEN-9090` |

### B14. `DELETE /hydrogen-generator` - excluir gerador A

| Campo | Valor para copiar |
|---|---|
| `serial_number` | `GEN-9080` |

## Vinculo entre cliente e gerador

### B15. `POST /asset` - criar vinculo A

| Campo | Valor para copiar |
|---|---|
| `customer_id` | valor anotado em `CUSTOMER_ID_B` |
| `generator_id` | valor anotado em `GENERATOR_ID_B` |
| `generator_qtd` | `2` |
| `installation_date` | `2026-09-22T09:00:00` |

Anote o `asset_id` da resposta como `ASSET_ID_A`.

### B16. `POST /asset` - criar vinculo B

| Campo | Valor para copiar |
|---|---|
| `customer_id` | valor anotado em `CUSTOMER_ID_B` |
| `generator_id` | valor anotado em `GENERATOR_ID_B` |
| `generator_qtd` | `4` |
| `installation_date` | `2026-09-22T10:00:00` |

Anote o `asset_id` da resposta como `ASSET_ID_B`.

### B17. `PUT /asset` - atualizar vinculo B

| Campo | Valor para copiar |
|---|---|
| `asset_id` | valor anotado em `ASSET_ID_B` |
| `customer_id` | valor anotado em `CUSTOMER_ID_B` |
| `generator_id` | valor anotado em `GENERATOR_ID_B` |
| `generator_qtd` | `5` |
| `installation_date` | `2026-09-22T10:00:00` |

### B18. `GET /assets` - listar os dois vinculos

Nao ha valor para preencher. A resposta deve incluir os vinculos `A` e `B`.

### B19. `GET /asset` - consultar vinculo B por ID

| Campo | Valor para copiar |
|---|---|
| `asset_id` | valor anotado em `ASSET_ID_B` |

### B20. `DELETE /asset` - excluir vinculo A

| Campo | Valor para copiar |
|---|---|
| `asset_id` | valor anotado em `ASSET_ID_A` |

## Integracoes executadas pela API principal

### B21. `POST /validate-address` - validar origem

Cole o corpo completo:

```json
{
  "customer_name": "Demonstracao Swagger 9090",
  "street1": "215 Clayton Street",
  "city": "San Francisco",
  "state": "CA",
  "zip_code": "94117"
}
```

### B22. `POST /validate-address` - validar destino

Cole o corpo completo:

```json
{
  "customer_name": "Destination Company",
  "street1": "20 West 34th Street",
  "city": "New York",
  "state": "NY",
  "zip_code": "10001"
}
```

### B23. `POST /shipping-quote`

Antes de colar, substitua o texto `COLE_O_GENERATOR_ID_B_AQUI` pelo numero
anotado em `GENERATOR_ID_B`. O valor deve ficar sem aspas.

```json
{
  "origin_name": "Demonstracao Swagger 9090",
  "origin_street": "215 Clayton Street",
  "origin_city": "San Francisco",
  "origin_state": "CA",
  "origin_zip": "94117",
  "customer_name": "Destination Company",
  "destination_street": "20 West 34th Street",
  "destination_city": "New York",
  "destination_state": "NY",
  "destination_zip": "10001",
  "generator_id": COLE_O_GENERATOR_ID_B_AQUI,
  "generator_quantity": 1
}
```

## Limpeza opcional depois da apresentacao

Os registros `A` ja foram excluidos durante os testes. Para nao deixar os
registros `B` no banco, repita as rotas de exclusao nesta ordem:

1. `DELETE /asset` com `asset_id = ASSET_ID_B`.
2. `DELETE /hydrogen-generator` com `serial_number = GEN-9090`.
3. `DELETE /customer` com `customer_id = CUSTOMER_ID_B`.

---

## Se algum dado ja existir

Uma resposta `409` indica conflito com um registro de teste anterior. Nesse
caso, conclua as exclusoes com os IDs existentes ou troque o sufixo `9090` em
todos estes valores:

```text
Nome:      Demonstracao Swagger 8080
E-mail:    demonstracao.swagger.8080@example.com
Tax ID:    808-08-8080
Gerador:   GEN-8080
```

Use sempre o mesmo novo sufixo durante toda a execucao.
