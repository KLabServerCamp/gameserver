# ヒント

## `command not found` が出たら

Codespace 起動直後のターミナルは、Python拡張が有効になる前に起動しているので、venvがactivateされていません。そのため、venv内にインストールされているコマンドを実行しようとしたら、 `command not found` や、 make であれば `No such file or directory` というエラーが発生します。

```bash
@methane ➜ /workspaces/gameserver (main) $ uvicorn
bash: uvicorn: command not found

@methane ➜ /workspaces/gameserver (main) $ make run
uvicorn app.api:app --reload
make: uvicorn: No such file or directory
make: *** [Makefile:2: run] Error 127
```

この場合は手動でvenvを有効にするか、一旦ターミナルを閉じてPythonのファイルを開いた状態で新しいターミナルを起動します。プロンプトの左端に `(gameserver)` と表示されていたらactivateが完了しています。

```bash
@methane ➜ /workspaces/gameserver (main) $ source venv/bin/activate
(gameserver) @methane ➜ /workspaces/gameserver (main) $ 
```

## mycli

標準のmysqlコマンドの代わりにmycliコマンドを使うと、色分けや補完が使えます。

mycliはvenvにインストールしているので、 `command not found` エラーになったら前の節を読みましょう。

