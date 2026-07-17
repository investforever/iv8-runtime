#pragma once

#include <memory>

#include "v8.h"

namespace iv8 {

// Owns the isolate-scoped resources for exactly one JSContext:
//   * one v8::ArrayBuffer::Allocator
//   * one v8::Isolate
//
// Phase 3 scope: creation and deterministic, non-throwing disposal only. No
// context, evaluation, or conversion logic lives here.
class IsolateHost {
public:
    IsolateHost();
    ~IsolateHost();

    IsolateHost(const IsolateHost&) = delete;
    IsolateHost& operator=(const IsolateHost&) = delete;

    v8::Isolate* isolate() const { return isolate_; }

private:
    // Declared before isolate_ so it is destroyed AFTER the isolate has been
    // disposed in the destructor body (the isolate uses the allocator).
    std::unique_ptr<v8::ArrayBuffer::Allocator> allocator_;
    v8::Isolate* isolate_ = nullptr;
};

}  // namespace iv8
