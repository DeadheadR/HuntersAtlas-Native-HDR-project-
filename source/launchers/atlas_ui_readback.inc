// Optional QA capture of the actual swapchain after Atlas and the native overlay.
void DumpAtlasUiFrameIfDue(const Instance& instance, Scheduler& scheduler, vk::CommandBuffer cmdbuf,
                          vk::Image image, u32 width, u32 height, vk::Format format) {
    static const char* trigger = std::getenv("BB_MAP_UI_DUMP_TRIGGER");
    static int index = 0;
    if (!trigger || std::remove(trigger) != 0) return;
    const vk::ImageSubresourceRange range{vk::ImageAspectFlagBits::eColor,0,1,0,1};
    const vk::ImageMemoryBarrier before{
        .srcAccessMask = vk::AccessFlagBits::eMemoryWrite,
        .dstAccessMask = vk::AccessFlagBits::eTransferRead,
        .oldLayout = vk::ImageLayout::ePresentSrcKHR,
        .newLayout = vk::ImageLayout::eGeneral,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image, .subresourceRange = range};
    cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eAllCommands,vk::PipelineStageFlagBits::eTransfer,
                           {},{},{},before);
    const bool bgra = format == vk::Format::eB8G8R8A8Unorm || format == vk::Format::eB8G8R8A8Srgb;
    DumpImages(instance,scheduler,cmdbuf,index++,{{image,width,height,4,"map-ui",bgra?"bgra":"rgba"}});
    const vk::ImageMemoryBarrier after{
        .srcAccessMask = vk::AccessFlagBits::eTransferRead,
        .dstAccessMask = vk::AccessFlagBits::eNone,
        .oldLayout = vk::ImageLayout::eGeneral,
        .newLayout = vk::ImageLayout::ePresentSrcKHR,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image, .subresourceRange = range};
    cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eTransfer,vk::PipelineStageFlagBits::eBottomOfPipe,
                           {},{},{},after);
}
