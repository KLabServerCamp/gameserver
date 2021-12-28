# マッチングルーム～ライブ～リザルト
## 要件
* 入場時に部屋を立てる or 部屋に入るを選択する
* 入る選択時
  * 現在立てられている部屋一覧を表示
    * 楽曲・入場状況（アイコンや参加可能人数とか）
      * 押下すると入る（確認ダイアログは挟む）
    * 更新ボタンを押下すると再度読みなおす
プレイヤーが選択可能な曲を表示
曲をタップすることで、シングル or マルチ の選択画面を表示
* 立てる選択時と入った後の画面
  * 入場しているプレイヤーの名前・キャラアイコンを表示。自分がどこであるかも表示
  * 立てた人限定で開始ボタンを表示。部屋の人数問わず押下可能
* ライブ中はポーズ不可、HPが0になっても続行

# API・構造体の定義
## Enum
### LiveDifficulty
| name | value | memo |
|---|---|---|
| normal | 1 |  |
| hard | 2  | |

### JoinRoomResult
| name | value | memo |
|---|---|---|
| Ok | 1 | 入場OK |
| RoomFull | 2  | 満員 |
| Disbanded | 3  | 解散済み |
| OtherError | 4  | その他エラー |

### WaitRoomStatus
| name | value | memo |
|---|---|---|
| Waiting | 1 | ホストがライブ開始ボタン押すのを待っている |
| LiveStart | 2  | ライブ画面遷移OK |
| Dissolution | 3  | 解散された |

## 構造体
### RoomInfo
| name | type | memo |
|---|---|---|
| room_id | int | 部屋識別子 |
| live_id  | int  | プレイ対象の楽曲識別子 |
| joined_user_count| int | 部屋に入っている人数 |
| max_user_count| int | 部屋の最大人数 |

### RoomUser
| name | type | memo |
|---|---|---|
| user_id  | int  | ユーザー識別子 |
| name | str | ユーザー名 |
| leader_card_id | int | 設定アバター |
| select_difficulty | LiveDifficulty | 選択難易度 |
| is_me | bool | リクエスト投げたユーザーと同じか ※user_idが事前にクライアントに返されるのであれば不要 |
| is_host | bool | 部屋を立てた人か |

### ResultUser
| name | type | memo |
|---|---|---|
| user_id  | int  | ユーザー識別子 |
| judge_count_list | list[int] | 各判定数（良い判定から昇順） |
| score | int | 獲得スコア |

## API（Path）
### /room/create
ルームを新規で建てる。

#### Request
| name | type | memo |
|---|---|---|
| live_id | int | ルームで遊ぶ楽曲のID |
| select_difficulty | LiveDifficulty | 選択難易度 |

#### Response
| name | type | memo |
|---|---|---|
| room_id | int | 発行されたルームのID（以後の通信はこのiDを添える） |

### /room/list
入場可能なルーム一覧を取得

#### Request
| name | type | memo |
|---|---|---|
| live_id | int | ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする） | 

#### Response
| name | type | memo |
|---|---|---|
| room_info_list | list[RoomInfo] | 入場可能なルーム一覧 |


### /room/join
上記listのルームに入場。

#### Request
| name | type | memo |
|---|---|---|
| room_id | int | 入るルーム |
| select_difficulty | LiveDifficulty | 選択難易度 |

#### Response
| name | type | memo |
|---|---|---|
| join_room_result | JoinRoomResult | ルーム入場結果 |


### /room/wait
ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。
クライアントはn秒間隔で投げる想定。

#### Request
| name | type | memo |
|---|---|---|
| room_id | int | 対象ルーム |

#### Response
| name | type | memo |
|---|---|---|
| status | WaitRoomStatus | 結果 |
| room_user_list | list[RoomUser]| ルームにいるプレイヤー一覧 |


### /room/start
ルームのライブ開始。部屋のオーナーがたたく。

#### Request
| name | type | memo |
|---|---|---|
| room_id | int | 対象ルーム |

#### Response
| name | type | memo |
|---|---|---|
| | | |


### /room/end
ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。

#### Request
| name | type | memo |
|---|---|---|
| room_id | int | 対象ルーム |
| judge_count_list | list[int] | 各判定数 |
| score | int | スコア |

#### Response
| name | type | memo |
|---|---|---|
| | | |


### /room/result
ルームのライブ終了後。end 叩いたあとにこれをポーリングする。
クライアントはn秒間隔で投げる想定。

#### Request
| name | type | memo |
|---|---|---|
| room_id | int | 対象ルーム |

#### Response
| name | type | memo |
|---|---|---|
| result_user_list | list[ResultUser] | 自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定 |
