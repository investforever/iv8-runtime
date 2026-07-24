#pragma once

#include <atomic>
#include <mutex>
#include <string>
#include <unordered_set>
#include <vector>

namespace iv8 {

// M9-2: one recorded host-method-call hit for the watch_apis observation面.
struct WatchHit {
    std::string path;           // the watched "receiver.method" path that was hit
    std::string resource_name;  // the executing script's resource name (may be "")
};

// M9-2: a minimal, Page-level record面 for watched host-method calls. Registration
// (set_paths) persists across a page's generations (repeated load); the current
// generation's ContextState holds a pointer to it so the host-method dispatch
// points can record hits. This phase records CALLS only (no breakpoints, no args /
// return / stack, no property watches). Read-and-clear semantics for the hit log.
//
// Thread-safety: host callbacks run on the isolate thread under the operation
// guard, while read_watch_api_hits() (take_hits) is a plain Python-thread call; a
// small mutex guards the hit log / paths / current-resource against a concurrent
// DevTools-driven dispatch. `enabled_` is atomic so the hot path can skip the lock.
class WatchRegistry {
public:
    // Replace the watched set (deduped) and enable recording. An empty list is a
    // valid "enabled, watches nothing" state.
    void set_paths(const std::vector<std::string>& paths) {
        std::lock_guard<std::mutex> lock(mutex_);
        paths_.clear();
        for (const std::string& path : paths) {
            paths_.insert(path);
        }
        enabled_.store(true, std::memory_order_release);
    }

    bool enabled() const { return enabled_.load(std::memory_order_acquire); }

    // Set / read the executing script's resource name (set around each eval).
    void set_current_resource(const std::string& name) {
        std::lock_guard<std::mutex> lock(mutex_);
        current_resource_ = name;
    }
    std::string current_resource() {
        std::lock_guard<std::mutex> lock(mutex_);
        return current_resource_;
    }

    // Record a hit if `path` is watched (else a no-op). `path` is the full
    // "receiver.method" string, e.g. "document.querySelector".
    void maybe_record(const std::string& path) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (paths_.find(path) == paths_.end()) {
            return;
        }
        hits_.push_back(WatchHit{path, current_resource_});
    }

    // Return the accumulated hits and clear the log (read-and-clear).
    std::vector<WatchHit> take_hits() {
        std::lock_guard<std::mutex> lock(mutex_);
        std::vector<WatchHit> out;
        out.swap(hits_);
        return out;
    }

private:
    mutable std::mutex mutex_;
    std::atomic<bool> enabled_{false};
    std::unordered_set<std::string> paths_;
    std::vector<WatchHit> hits_;
    std::string current_resource_;
};

}  // namespace iv8
