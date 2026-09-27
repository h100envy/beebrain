# the telegram bot

the field in a chat. the same bee, the same live pools, the same forward test as `/trade`, plus a paper account for
every telegram user.

## what it does

| you send | the bee answers |
| --- | --- |
| any contract address | its verdict on that pool right now: PASS, WATCH or SKIP, the reflexes that tripped, one value per lobe, buttons for a paper buy and the chart |
| `/scan` | the best pools it scored in the last minutes, each CA in a tap to copy block |
| `/alerts on` | a message for every PASS on your chain, at most one every 15 seconds |
| `/buy <CA or $SYMBOL> 50` | a paper buy, $500 to start, the same fills and exits as the site |
| `/sell 1`, `/me` | close a position, see your account. you get a message when an exit fires |
| `/race` | you, the bee and random, the forward test and the graduation gate |
| `/chain base` | switch chain, if the bot runs more than one |

scoring a pasted CA has no side effects: the pool is not traded by the bee and does not enter the forward test, so
people poking at the bot cannot tilt the numbers.

## run it

1. in telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, pick a name and a username ending in `bot`.
2. put the token it gives you in a file only you can read:

   ```
   mkdir -p ~/.beebrain && nano ~/.beebrain/bot.token && chmod 600 ~/.beebrain/bot.token
   ```

   or set `BEEBRAIN_BOT_TOKEN`. never commit it.
3. start it:

   ```
   beebrain bot --chains solana,base
   beebrain bot --chains solana --channel @yoursignalschannel     # also post every PASS to a channel
   ```

   for a channel, add the bot to the channel as an admin first.

the bot uses long polling, so it needs a machine that stays on: your own computer while it is awake, or any small
server. state lives in `~/.beebrain/bot.json` and `~/.beebrain/bot-field-<chain>.json`, and survives restarts.

## boundaries

- read only market data from dexscreener and geckoterminal. no wallets, no keys, no orders.
- every message about a pool says paper and not advice.
- token names come from public apis and anyone can set them: the bot escapes them before they reach telegram's html.
