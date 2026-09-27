# Bella Pele Cosméticos — Sistema com banco de dados (SQLite)

Este pacote conecta o site que fizemos a um banco de dados de verdade, usando
**SQLite** (um arquivo `.db` local) através de um pequeno backend em
**Python + Flask**. Assim, os dados deixam de sumir quando você recarrega a
página — e você pode abrir e conferir tudo com o **DB Browser for SQLite**.

## Estrutura da pasta

```
bella-pele-backend/
├── app.py              -> backend (rotas da API + banco de dados)
├── requirements.txt    -> dependências Python
├── index.html          -> o site (frontend) servido pelo Flask
└── bella_pele.db        -> criado automaticamente na 1ª execução
```

## 1. Pré-requisitos

- **Python 3.9 ou mais recente** instalado ([python.org](https://www.python.org/downloads/))
- (opcional, mas recomendado) **DB Browser for SQLite** instalado
  ([sqlitebrowser.org](https://sqlitebrowser.org/dl/)) para visualizar o banco

## 2. Instalação

Abra um terminal dentro da pasta `bella-pele-backend` e rode:

```bash
pip install -r requirements.txt
```

Isso instala o Flask (o "servidor" que vai rodar o site) e o Werkzeug (que
cuida do hash das senhas).

## 3. Rodando o sistema

Ainda no terminal, dentro da pasta `bella-pele-backend`:

```bash
python app.py
```

Você verá algo como `Running on http://127.0.0.1:5000`. Abra esse endereço no
navegador — o site vai carregar normalmente, só que agora **tudo que você
salvar fica gravado no arquivo `bella_pele.db`**, que é criado
automaticamente na pasta na primeira vez que você roda o `app.py`.

Para parar o servidor, volte ao terminal e aperte `Ctrl + C`.

### Usuário de teste

Na primeira execução, o sistema cria automaticamente este usuário na tabela
`usuarios` (se ele ainda não existir):

- Email: `teste@bellapele.com`
- Senha: `Teste@123`

As senhas são armazenadas somente como hash.

### Publicando temporariamente com ngrok

Com o Flask rodando em um terminal, abra outro terminal na mesma pasta e
execute:

```powershell
ngrok http 5000
```

Abra no navegador a URL `https://...ngrok...` exibida pelo ngrok. O processo do
Flask precisa continuar rodando enquanto o endereço público estiver em uso.

Para escolher outra porta local, por exemplo:

```powershell
$env:FLASK_PORT = "8000"
python app.py
ngrok http 8000
```

O host, a porta e o modo debug também podem ser configurados pelas variáveis
`FLASK_HOST`, `FLASK_PORT` e `FLASK_DEBUG`. O debug fica desativado por padrão.

## 4. Abrindo o banco no DB Browser for SQLite

1. Abra o **DB Browser for SQLite**
2. Clique em **"Open Database"**
3. Selecione o arquivo `bella_pele.db` dentro da pasta `bella-pele-backend`
4. Na aba **"Browse Data"**, escolha a tabela que quer ver no menu suspenso
   (`clientes`, `produtos`, `funcionarios`, `vendas`, `financeiro`,
   `usuarios`)

> ⚠️ **Importante:** feche o site (ou pare o `app.py`) antes de editar dados
> diretamente pelo DB Browser e salvar (**Write Changes**), pra evitar que os
> dois programas tentem escrever no arquivo ao mesmo tempo. Depois de editar
> e salvar no DB Browser, dê **F5**/recarregue o site pra ver a mudança.

## 5. O que já está implementado no backend

- **Cadastro e login de usuários**, com a senha guardada como **hash**
  (nunca em texto puro) na tabela `usuarios`.
- **Bloqueio de login**: depois de **3 tentativas erradas** com o mesmo
  email, o sistema bloqueia novos logins por **60 segundos** — o contador
  aparece na própria tela de login. Isso é controlado pelas colunas
  `tentativas_falhas` e `bloqueado_ate` da tabela `usuarios`.
- **Clientes, Produtos e Funcionários**: cadastro e pesquisa gravando direto
  no banco.
- **Vendas**: ao salvar uma venda, o backend automaticamente cria também um
  lançamento de **Entrada** na tabela `financeiro`, ligado à venda pela
  coluna `venda_id` — é assim que a venda aparece na tela Financeiro.
- **Financeiro**: cadastro de lançamentos com vencimento e status
  (Pago/Pendente), resumo de entradas/saídas, gráfico e abas de
  contas a vencer / vencidas / pagas.

## 6. Próximos passos possíveis

- Hospedar isso num serviço como Railway, Render ou PythonAnywhere pra
  acessar de qualquer lugar (hoje só funciona na sua máquina, em
  `127.0.0.1`).
- Trocar a chave `app.secret_key` no `app.py` por uma variável de ambiente
  antes de colocar em produção.
- Adicionar edição/exclusão de registros (hoje o sistema cadastra e
  pesquisa, mas não edita/apaga pela tela — dá pra fazer isso direto no
  DB Browser por enquanto).

Qualquer dúvida ou se quiser que eu implemente algum desses próximos passos,
é só pedir.
