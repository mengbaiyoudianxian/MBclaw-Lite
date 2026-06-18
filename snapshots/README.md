# Snapshots Directory

This directory saves point-in-time snapshots of conversation state.

## Purpose

- Preserve conversation state at specific moments
- Enable rollback to previous states
- Support versioning of conversation data

## Snapshot Types

- **Full Snapshots**: Complete conversation state
- **Incremental Snapshots**: Changes since last snapshot
- **Manual Snapshots**: User-created checkpoints

## File Naming

Snapshots follow this pattern:
- `snapshot_YYYY-MM-DD_HH-MM-SS.json` - Timestamped snapshots
- `snapshot_version_N.json` - Version-numbered snapshots

## Usage

Snapshots are typically created:
- Before major changes
- At regular intervals
- On user request
- Before system updates