# hermes.base.storage

The module is responsible for high-performance asynchronous file IO. 
It periodically spins up coroutines to offset long IO operations with concurrent writes of different files.

[`storage_interface`](#hermes.base.storage.storage_interface) - base interface for Storage function.

[`storage`](#hermes.base.storage.storage) - concrete FSM-based Storage with streaming and dumping features.

[`storage_states`](#hermes.base.storage.storage_states) - FSM states of the Storage.

## ::: hermes.base.storage.storage_interface

## ::: hermes.base.storage.storage

## ::: hermes.base.storage.storage_states
