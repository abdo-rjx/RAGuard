package com.ragguard.orchestrator.service;

import com.ragguard.orchestrator.client.FastApiClient;
import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.ChatDtos;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class ChatService {

    private final FastApiClient fastApiClient;

    public ChatDtos.ChatResponse chat(String token, ChatDtos.ChatRequest request, User user) {
        log.info("User {} sending chat message", user.getUsername());
        return fastApiClient.chat(token, request).block();
    }

    public Flux<String> chatStream(String token, ChatDtos.ChatRequest request, User user) {
        log.info("User {} starting streaming chat", user.getUsername());
        return fastApiClient.chatStream(token, request);
    }

    public ChatDtos.ConversationResponse createConversation(String token, ChatDtos.CreateConversationRequest request, User user) {
        return fastApiClient.createConversation(token, request).block();
    }

    public List<ChatDtos.ConversationResponse> getConversations(String token, User user) {
        return fastApiClient.getConversations(token).block();
    }

    public List<ChatDtos.MessageResponse> getConversationMessages(String token, Long conversationId, User user) {
        return fastApiClient.getConversationMessages(token, conversationId).block();
    }

    public void submitFeedback(String token, ChatDtos.FeedbackRequest request, User user) {
        fastApiClient.submitFeedback(token, request).block();
    }
}