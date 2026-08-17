package com.ragguard.orchestrator.controller;

import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.model.dto.ChatDtos;
import com.ragguard.orchestrator.security.UserPrincipal;
import com.ragguard.orchestrator.service.ChatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;

import java.util.List;

@RestController
@RequestMapping("/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    @PostMapping
    public ResponseEntity<ChatDtos.ChatResponse> chat(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody ChatDtos.ChatRequest request) {

        ChatDtos.ChatResponse response = chatService.chat(userPrincipal.getToken(), request, toUser(userPrincipal));
        return ResponseEntity.ok(response);
    }

    @PostMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chatStream(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody ChatDtos.ChatRequest request) {

        return chatService.chatStream(userPrincipal.getToken(), request, toUser(userPrincipal));
    }

    @PostMapping("/conversations")
    public ResponseEntity<ChatDtos.ConversationResponse> createConversation(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody ChatDtos.CreateConversationRequest request) {

        ChatDtos.ConversationResponse response = chatService.createConversation(userPrincipal.getToken(), request, toUser(userPrincipal));
        return ResponseEntity.ok(response);
    }

    @GetMapping("/conversations")
    public ResponseEntity<List<ChatDtos.ConversationResponse>> getConversations(
            @AuthenticationPrincipal UserPrincipal userPrincipal) {

        List<ChatDtos.ConversationResponse> conversations = chatService.getConversations(userPrincipal.getToken(), toUser(userPrincipal));
        return ResponseEntity.ok(conversations);
    }

    @GetMapping("/conversations/{id}/messages")
    public ResponseEntity<List<ChatDtos.MessageResponse>> getConversationMessages(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @PathVariable Long id) {

        List<ChatDtos.MessageResponse> messages = chatService.getConversationMessages(userPrincipal.getToken(), id, toUser(userPrincipal));
        return ResponseEntity.ok(messages);
    }

    @PostMapping("/feedback")
    public ResponseEntity<Void> submitFeedback(
            @AuthenticationPrincipal UserPrincipal userPrincipal,
            @Valid @RequestBody ChatDtos.FeedbackRequest request) {

        chatService.submitFeedback(userPrincipal.getToken(), request, toUser(userPrincipal));
        return ResponseEntity.ok().build();
    }

    private User toUser(UserPrincipal principal) {
        return User.builder()
                .id(principal.getId())
                .username(principal.getUsername())
                .role(principal.getRole())
                .department(principal.getDepartment())
                .build();
    }
}