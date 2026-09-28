# the telegram bot

the field in a chat. the same bee, the same live pools, the same forward test as `/trade`, plus a paper account for
every telegram user.

## what it does

| you send | the bee answers |
| --- | --- |
| any contract address | its verdict on that pool right now: PASS, WATCH or SKIP, the reflexes that tripped, one value per lobe, buttons for a paper buy and the chart |
| `/scan` | the best pools it scored in the last minutes, each CA in a tap to copy block |
| `/history`, `/history pass 2` | latest scored pools and outcomes, with verdict filters and five entries per page |
| `/status` | command menu, last telegram poll, field tick and feed status |
| `/alerts on` | a message for every PASS on your chain, at most one every 15 seconds |
| `/buy <CA or $SYMBOL> 50` | a paper buy, $500 to start, the same fills and exits as the site |
| `/sell 1`, `/me` | close a position, see your account. you get a message when an exit fires |
| `/race` | you, the bee and random, the forward test and the graduation gate |
| `/chain robinhood` | switch to Robinhood Chain; the bot can also be configured for Solana, Base and BSC |

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
   beebrain bot --chains solana,robinhood
   beebrain bot --chains solana,robinhood --channel @yoursignalschannel     # also post every PASS to a channel
   ```

   for a channel, add the bot to the channel as an admin first.

Robinhood Chain is enabled alongside Solana by default; pass `--chains` to select other networks. The bot uses long polling, so it needs a machine that stays on: your own computer while it is awake, or any small
server. state lives in `~/.beebrain/bot.json` and `~/.beebrain/bot-field-<chain>.json`, and survives restarts.

## signal history

`/history` shows every verdict in scoring order, newest first. `/history pass` filters PASS;
`/history skip 2` opens the second page of SKIPs. wins and losses use the same calculation.

- pending: entry price and target time. the default horizon is 15 minutes.
- resolved: entry price, observed price, actual observation time, price return and return after the 2% round-trip fee model.
- unavailable: no usable price when the forward test expires, 20 minutes after its target. excluded from return statistics and counted separately.

this is a forward price evaluation, not an executed trade. it excludes slippage, unlike the paper account.
feeds can arrive late: use the displayed observation time, not an assumption of an exact 15-minute fill.
the latest 1,000 scored pools per chain are kept in the state file, including pending and unavailable entries.
all-time aggregates can include older pools outside this window. older state files still load, but cannot
reconstruct detailed history that was never saved. pasted addresses do not enter this ledger.
state is saved every minute and on a clean exit; a hard crash can lose the most recent unsaved minute.

the browser's existing forward test is unchanged. this release adds the persisted ledger to the python field and telegram bot.

## when commands do not appear

send `/start` and `/scan` manually. a missing command menu does not have to prevent replies.
on startup the bot registers the full command list and the commands button. a failed registration is retried
every minute while polling continues. temporary connection failures also retry; invalid credentials or a polling
conflict stop the process with a short diagnostic. check for another running copy or an existing webhook before restarting.

on the machine with the token, run this read-only check:

```
beebrain bot --check
beebrain bot --check --token-file /path/to/bot.token
```

it checks identity, missing default commands, the default menu button and whether a webhook is active.
it never consumes messages, resets a webhook, changes a menu or sends a message. it does not prove that a polling
process is running or that a particular chat has no command-scope override. exit 0 means these configuration checks
passed; exit 1 means a configuration issue; exit 2 means invalid arguments, credentials or an api/transport failure.
then test `/start`, `/status` and `/history` in telegram. compare the username from the check with the bot you opened.

## supervised linux service

[deploy/beebrain-bot.service](../deploy/beebrain-bot.service) is a template, not an installed service.
it expects a dedicated `beebrain` user and group, the checkout and its virtual environment at `/opt/beebrain`,
and a token file at `/etc/beebrain/bot.token` readable only by that service user. adapt those paths before installation.
`--state-dir /var/lib/beebrain` keeps the bot state under the service account. when migrating an existing bot,
stop the old instance first and copy its `bot.json` and `bot-field-*.json` into that directory with ownership
set to the service user. do not run two pollers for the same token.

after preparing the user, paths, dependencies and token on the server:

```
sudo cp deploy/beebrain-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now beebrain-bot
sudo systemctl status beebrain-bot
sudo journalctl -u beebrain-bot -n 100 --no-pager
```

the service restarts after process failures, waits 10 seconds, and limits repeated restarts.
stopping the service sends SIGINT so the bot can stop its field worker and save.
the mac used for development does not run systemd; this template must be installed on the linux host.

## boundaries

- read only market data from dexscreener and geckoterminal. no wallets, no keys, no orders.
- every message about a pool says paper and not advice.
- token names come from public apis and anyone can set them: the bot escapes them before they reach telegram's html.
