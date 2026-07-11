UPDATE vpn_nodes
SET region = '美国犹他', updated_at = CURRENT_TIMESTAMP
WHERE id = 'node-144';

UPDATE vpn_nodes
SET region = '美国达拉斯', updated_at = CURRENT_TIMESTAMP
WHERE id = 'node-172';
