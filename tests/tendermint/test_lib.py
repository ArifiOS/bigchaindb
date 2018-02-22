import os
import time
from unittest.mock import patch

import pytest

from bigchaindb import backend


pytestmark = pytest.mark.tendermint


def test_asset_is_separated_from_transaciton(b):
    from bigchaindb.models import Transaction
    from bigchaindb.common.crypto import generate_key_pair

    alice = generate_key_pair()
    bob = generate_key_pair()

    asset = {'Never gonna': ['give you up',
                             'let you down',
                             'run around'
                             'desert you',
                             'make you cry',
                             'say goodbye',
                             'tell a lie',
                             'hurt you']}

    tx = Transaction.create([alice.public_key],
                            [([bob.public_key], 1)],
                            metadata=None,
                            asset=asset)\
                    .sign([alice.private_key])

    b.store_transaction(tx)
    assert 'asset' not in backend.query.get_transaction(b.connection, tx.id)
    assert backend.query.get_asset(b.connection, tx.id)['data'] == asset
    assert b.get_transaction(tx.id) == tx


@pytest.mark.bdb
def test_get_latest_block(tb):
    from bigchaindb.tendermint.lib import Block

    b = tb
    for i in range(10):
        app_hash = os.urandom(16).hex()
        txn_id = os.urandom(16).hex()
        block = Block(app_hash=app_hash, height=i,
                      transactions=[txn_id])._asdict()
        b.store_block(block)

    block = b.get_latest_block()
    assert block['height'] == 9


def test_validation_error(b):
    from bigchaindb.models import Transaction
    from bigchaindb.common.crypto import generate_key_pair

    alice = generate_key_pair()
    tx = Transaction.create([alice.public_key],
                            [([alice.public_key], 1)],
                            asset=None)\
                    .sign([alice.private_key]).to_dict()

    tx['metadata'] = ''
    assert not b.validate_transaction(tx)


@patch('requests.post')
def test_write_and_post_transaction(mock_post, b):
    from bigchaindb.models import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    from bigchaindb.tendermint.utils import encode_transaction

    alice = generate_key_pair()
    tx = Transaction.create([alice.public_key],
                            [([alice.public_key], 1)],
                            asset=None)\
                    .sign([alice.private_key]).to_dict()

    tx = b.validate_transaction(tx)
    b.write_transaction(tx, 'broadcast_tx_async')

    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert 'broadcast_tx_async' == kwargs['json']['method']
    encoded_tx = [encode_transaction(tx.to_dict())]
    assert encoded_tx == kwargs['json']['params']


@patch('requests.post')
@pytest.mark.parametrize('mode', [
    'broadcast_tx_async',
    'broadcast_tx_sync',
    'broadcast_tx_commit'
])
def test_post_transaction_valid_modes(mock_post, b, mode):
    from bigchaindb.models import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    alice = generate_key_pair()
    tx = Transaction.create([alice.public_key],
                            [([alice.public_key], 1)],
                            asset=None) \
        .sign([alice.private_key]).to_dict()
    tx = b.validate_transaction(tx)
    b.write_transaction(tx, mode)

    args, kwargs = mock_post.call_args
    assert mode == kwargs['json']['method']


def test_post_transaction_invalid_mode(b):
    from bigchaindb.models import Transaction
    from bigchaindb.common.crypto import generate_key_pair
    from bigchaindb.common.exceptions import ValidationError
    alice = generate_key_pair()
    tx = Transaction.create([alice.public_key],
                            [([alice.public_key], 1)],
                            asset=None) \
        .sign([alice.private_key]).to_dict()
    tx = b.validate_transaction(tx)
    with pytest.raises(ValidationError):
        b.write_transaction(tx, 'nope')


def test_get_validator_updates(b, validator_pub_key):
    from bigchaindb.backend import query

    # create a validator update object
    validator_update = gen_validator_update(validator_pub_key, 10)
    query.store_validator_update(b.connection, validator_update)

    ids, updates = b.get_validator_updates()
    assert updates == validator_update['validators']


def test_get_multiple_validator_updates(b, validator_pub_key):
    from bigchaindb.backend import query

    # create a validator update object
    v1 = gen_validator_update(validator_pub_key, 10)
    query.store_validator_update(b.connection, v1)

    time.sleep(1)
    v2 = gen_validator_update(validator_pub_key, 20)
    query.store_validator_update(b.connection, v2)

    ids, updates = b.get_validator_updates()
    assert updates == v2['validators']


def gen_validator_update(key, power):
    validator = [{'pub_key': {'type': 'ed25519',
                              'data': key},
                  'power': power}]
    return {'validators': validator, 'sync': True}
