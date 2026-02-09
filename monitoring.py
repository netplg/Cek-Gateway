import os
import time
import random
import socket
import smtplib
from email.mime.text import MIMEText
from collections import defaultdict, deque

# ================= CONFIG =================

SERVER_TEST = ["8.8.8.8", "8.8.4.4"]
DOMAINS = ["netplg.com", "ui.ac.id", "itb.ac.id"]

DNS_SERVER = "1.1.1.1"
DNS_PORT = 53

PING_RTO_THRESHOLD = 2
PING_IDLE_TO_DOWN = 3
PING_WINDOW_SEC = 10

DNS_FAIL_TO_IDLE = 2
DNS_IDLE_TO_DOWN = 3

EMAIL_INTERVAL = 10
LOOP_INTERVAL = 1

# ===== Gmail SMTP =====
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "yourgmail@gmail.com"
SMTP_PASS = "APP_PASSWORD"
EMAIL_TO = "tujuan@email.com"

# ================= STORAGE =================

ping_rto_log = defaultdict(lambda: deque())
ping_idle_counter = defaultdict(int)
ping_status = defaultdict(lambda: "UP")

dns_fail_counter = defaultdict(int)
dns_idle_counter = defaultdict(int)
dns_status = defaultdict(lambda: "UP")

email_status = "NOT_SENT"
loop_counter = 0

# ================= FUNCTION =================

def ping_host(host):
    res = os.system("ping -c 1 -W 1 " + host + " > /dev/null 2>&1")
    return res == 0


def dns_udp_check():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto("\x00", (DNS_SERVER, DNS_PORT))
        s.close()
        return True
    except:
        return False


def dns_tcp_check():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect((DNS_SERVER, DNS_PORT))
        s.close()
        return True
    except:
        return False


def send_email(subject, body):
    global email_status
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = EMAIL_TO

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
        server.quit()

        email_status = "SENT"
        return True

    except Exception as e:
        email_status = "ERROR: " + str(e)
        return False


# ================= MAIN LOOP =================

while True:

    loop_counter += 1
    print "\n=============================="
    print "LOOP:", loop_counter

    # ================= PING CHECK =================
    srv = random.choice(SERVER_TEST)
    now = time.time()

    if ping_host(srv):
        ping_status[srv] = "UP"
        ping_idle_counter[srv] = 0
        ping_rto_log[srv].clear()

    else:
        ping_rto_log[srv].append(now)

        while ping_rto_log[srv] and now - ping_rto_log[srv][0] > PING_WINDOW_SEC:
            ping_rto_log[srv].popleft()

        if len(ping_rto_log[srv]) >= PING_RTO_THRESHOLD:
            ping_status[srv] = "IDLE"
            ping_idle_counter[srv] += 1
            ping_rto_log[srv].clear()

            if ping_idle_counter[srv] >= PING_IDLE_TO_DOWN:
                ping_status[srv] = "DOWN"

    # ================= DNS CHECK =================
    udp_ok = dns_udp_check()
    tcp_ok = dns_tcp_check()

    for domain in DOMAINS:

        if udp_ok or tcp_ok:
            dns_status[domain] = "UP"
            dns_fail_counter[domain] = 0
            dns_idle_counter[domain] = 0

        else:
            dns_fail_counter[domain] += 1

            if dns_fail_counter[domain] >= DNS_FAIL_TO_IDLE:
                dns_status[domain] = "IDLE"
                dns_idle_counter[domain] += 1
                dns_fail_counter[domain] = 0

                if dns_idle_counter[domain] >= DNS_IDLE_TO_DOWN:
                    dns_status[domain] = "DOWN"

    # ================= REKAP =================
    print "\n--- REKAP PING ---"
    for s in SERVER_TEST:
        print s, ":", ping_status[s], "(IdleCount=", ping_idle_counter[s], ")"

    print "\n--- REKAP DNS ---"
    for d in DOMAINS:
        print d, ":", dns_status[d], "(IdleCount=", dns_idle_counter[d], ")"

    # ================= REKOMENDASI =================
    print "\n--- REKOMENDASI ---"

    for s in SERVER_TEST:
        if ping_status[s] == "DOWN":
            print s, "-> CEK INTERNET"

    for d in DOMAINS:
        if dns_status[d] == "DOWN":
            print d, "-> CEK DNS SERVER"

    # ================= EMAIL ALERT =================
    if loop_counter % EMAIL_INTERVAL == 0:

        body = ""

        for s in SERVER_TEST:
            if ping_status[s] == "DOWN":
                body += "PING DOWN : " + s + "\n"

        for d in DOMAINS:
            if dns_status[d] == "DOWN":
                body += "DNS DOWN : " + d + "\n"

        if body != "":
            send_email("NETWORK ALERT STATUS", body)

    print "\nEmail Status:", email_status

    time.sleep(LOOP_INTERVAL)
