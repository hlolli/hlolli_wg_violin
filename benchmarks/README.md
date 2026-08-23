# Benchmarks

Benchmarks record cost on a named host. They do not set one speed target for
all machines.

## Release loads

`release_loads.csd` covers one closed string, one bowed string with three open
rails, a double stop, and eight separate players. Run the saved comparison:

```sh
cmake --build build --target benchmark_release
```

The runner uses seven samples, compares the median child CPU time, and rejects
a result above 120 percent of the matching saved value. It also checks the
host, Csound build, duration, and case set before comparing.

## Bow contact

```sh
cmake --build build --target benchmark_bow_contact
```

This measures silence, one bowed string, four strings on one handle, and four
strings on four handles. It reports the median. It does not fail on speed.

## Sympathetic strings

```sh
cmake --build build --target benchmark_sympathetic
```

This compares the neutral path, open-string bridge drive, and both ends of
`kStrange`.

`release_reference.json` holds the fixed native record.
`wasm_release_budget.json` holds browser source and plug-in size limits.
