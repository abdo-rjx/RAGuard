package com.ragguard.orchestrator.model.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

public class ChatDtos {

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ChatRequest {
        @NotBlank
        @Size(max = 4000)
        private String message;

        private Long conversationId;

        @Builder.Default
        private boolean stream = true;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ChatResponse {
        private String response;
        private Long conversationId;
        private List<SourceInfo> sources;
        private long latencyMs;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SourceInfo {
        private Long documentId;
        private String title;
        private String snippet;
        private double score;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ConversationResponse {
        private Long id;
        private String title;
        private Long userId;
        private java.time.Instant createdAt;
        private java.time.Instant updatedAt;
        private int messageCount;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class MessageResponse {
        private Long id;
        private Long conversationId;
        private String role; // user, assistant
        private String content;
        private List<SourceInfo> sources;
        private java.time.Instant createdAt;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class FeedbackRequest {
        @NotBlank
        private String messageId;

        @NotBlank
        private String feedback; // helpful, not_helpful, security_concern

        private String comment;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CreateConversationRequest {
        @NotBlank
        @Size(max = 200)
        private String title;
    }
}