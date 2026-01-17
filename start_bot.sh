#!/bin/bash
cd ~/CashDeals_bot
source venv/bin/activate
nohup python main.py > bot.log 2>&1 &
echo "Bot started with PID: $!"
echo "Logs: tail -f ~/CashDeals_bot/bot.log"


