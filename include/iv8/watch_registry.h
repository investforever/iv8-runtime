#pragma once

#include <atomic>
#include <functional>
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
    // Replace the watched set (deduped), set the break-on-hit mode, and enable
    // recording. An empty list is a valid "enabled, watches nothing" state.
    void set_paths(const std::vector<std::string>& paths, bool break_on_hit) {
        std::lock_guard<std::mutex> lock(mutex_);
        paths_.clear();
        for (const std::string& path : paths) {
            paths_.insert(path);
        }
        break_on_hit_ = break_on_hit;
        enabled_.store(true, std::memory_order_release);
    }

    bool enabled() const { return enabled_.load(std::memory_order_acquire); }

    // M9-3: install the "request an Inspector pause" callback (set once by
    // PageState). Invoked by maybe_record() on a matched hit when break-on-hit is
    // on; a no-op if unset or if no Inspector session is attached (口径 1).
    void set_pause_requester(std::function<void()> requester) {
        std::lock_guard<std::mutex> lock(mutex_);
        pause_requester_ = std::move(requester);
    }

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
    // "receiver.method" string, e.g. "document.querySelector". On a matched hit in
    // break-on-hit mode, the pause requester (if any) is invoked AFTER the lock is
    // released (it enters the V8 Inspector, so it must not run under the mutex).
    void maybe_record(const std::string& path) {
        std::function<void()> pause;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (paths_.find(path) == paths_.end()) {
                return;
            }
            hits_.push_back(WatchHit{path, current_resource_});
            if (break_on_hit_) {
                pause = pause_requester_;  // copy under the lock
            }
        }
        if (pause) {
            pause();
        }
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
    bool break_on_hit_ = false;
    std::unordered_set<std::string> paths_;
    std::vector<WatchHit> hits_;
    std::string current_resource_;
    std::function<void()> pause_requester_;
};

}  // namespace iv8
