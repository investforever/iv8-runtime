#include "iv8/isolate_host.h"

namespace iv8 {

IsolateHost::IsolateHost() {
    allocator_.reset(v8::ArrayBuffer::Allocator::NewDefaultAllocator());

    v8::Isolate::CreateParams params;
    params.array_buffer_allocator = allocator_.get();
    isolate_ = v8::Isolate::New(params);
}

IsolateHost::~IsolateHost() {
    // Deterministic, non-throwing teardown. Dispose the isolate while the
    // allocator is still alive; the allocator is released afterwards when the
    // member is destroyed.
    if (isolate_ != nullptr) {
        isolate_->Dispose();
        isolate_ = nullptr;
    }
}

}  // namespace iv8
