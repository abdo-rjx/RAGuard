package com.ragguard.orchestrator.client;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ragguard.orchestrator.model.dto.ChatDtos;
import com.ragguard.orchestrator.model.dto.DocumentDtos;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class FastApiClient {

    private final WebClient fastApiWebClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // Chat endpoints
    public Mono<ChatDtos.ChatResponse> chat(String token, ChatDtos.ChatRequest request) {
        return fastApiWebClient.post()
                .uri("/chat")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatDtos.ChatResponse.class)
                .timeout(Duration.ofSeconds(60))
                .onErrorResume(e -> {
                    log.error("FastAPI chat error: {}", e.getMessage());
                    return Mono.error(new RuntimeException("Chat service unavailable: " + e.getMessage()));
                });
    }

    public Flux<String> chatStream(String token, ChatDtos.ChatRequest request) {
        return fastApiWebClient.post()
                .uri("/chat/stream")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(String.class)
                .timeout(Duration.ofSeconds(120))
                .onErrorResume(e -> {
                    log.error("FastAPI chat stream error: {}", e.getMessage());
                    return Flux.error(new RuntimeException("Chat stream unavailable: " + e.getMessage()));
                });
    }

    public Mono<ChatDtos.ConversationResponse> createConversation(String token, ChatDtos.CreateConversationRequest request) {
        return fastApiWebClient.post()
                .uri("/conversations")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(ChatDtos.ConversationResponse.class);
    }

    public Mono<List<ChatDtos.ConversationResponse>> getConversations(String token) {
        return fastApiWebClient.get()
                .uri("/conversations")
                .header("Authorization", "Bearer " + token)
                .retrieve()
                .bodyToFlux(ChatDtos.ConversationResponse.class)
                .collectList();
    }

    public Mono<List<ChatDtos.MessageResponse>> getConversationMessages(String token, Long conversationId) {
        return fastApiWebClient.get()
                .uri("/conversations/{id}/messages", conversationId)
                .header("Authorization", "Bearer " + token)
                .retrieve()
                .bodyToFlux(ChatDtos.MessageResponse.class)
                .collectList();
    }

    public Mono<Void> submitFeedback(String token, ChatDtos.FeedbackRequest request) {
        return fastApiWebClient.post()
                .uri("/chat/feedback")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .toBodilessEntity()
                .then();
    }

    // Document endpoints
    public Mono<DocumentDtos.UploadResponse> uploadDocument(String token, String title, String department,
                                                            String classificationLevel, byte[] fileContent, String fileName) {
        return fastApiWebClient.post()
                .uri(uriBuilder -> uriBuilder
                        .path("/documents/upload")
                        .queryParam("title", title)
                        .queryParam("department", department)
                        .queryParam("classification_level", classificationLevel)
                        .build())
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(createMultipartBody(fileContent, fileName))
                .retrieve()
                .bodyToMono(DocumentDtos.UploadResponse.class);
    }

    public Mono<DocumentDtos.DocumentListResponse> listDocuments(String token, int page, int size) {
        return fastApiWebClient.get()
                .uri(uriBuilder -> uriBuilder
                        .path("/documents")
                        .queryParam("page", page)
                        .queryParam("size", size)
                        .build())
                .header("Authorization", "Bearer " + token)
                .retrieve()
                .bodyToMono(DocumentDtos.DocumentListResponse.class);
    }

    public Mono<DocumentDtos.DocumentResponse> getDocument(String token, Long documentId) {
        return fastApiWebClient.get()
                .uri("/documents/{id}", documentId)
                .header("Authorization", "Bearer " + token)
                .retrieve()
                .bodyToMono(DocumentDtos.DocumentResponse.class);
    }

    public Mono<Void> deleteDocument(String token, Long documentId) {
        return fastApiWebClient.delete()
                .uri("/documents/{id}", documentId)
                .header("Authorization", "Bearer " + token)
                .retrieve()
                .toBodilessEntity()
                .then();
    }

    public Mono<DocumentDtos.DocumentResponse> updateDocument(String token, Long documentId, DocumentDtos.UpdateDocumentRequest request) {
        return fastApiWebClient.patch()
                .uri("/documents/{id}", documentId)
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToMono(DocumentDtos.DocumentResponse.class);
    }

    public Mono<List<DocumentDtos.SearchResult>> searchDocuments(String token, DocumentDtos.SearchRequest request) {
        return fastApiWebClient.post()
                .uri("/documents/search")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(DocumentDtos.SearchResult.class)
                .collectList();
    }

    public Mono<Void> reindexDocuments(String token, DocumentDtos.ReindexRequest request) {
        return fastApiWebClient.post()
                .uri("/documents/reindex")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .toBodilessEntity()
                .then();
    }

    // Health check
    public Mono<Boolean> healthCheck() {
        return fastApiWebClient.get()
                .uri("/health")
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> "ok".equals(response.get("status")))
                .onErrorReturn(false)
                .timeout(Duration.ofSeconds(5));
    }

    private org.springframework.util.MultiValueMap<String, Object> createMultipartBody(byte[] fileContent, String fileName) {
        org.springframework.util.LinkedMultiValueMap<String, Object> body = new org.springframework.util.LinkedMultiValueMap<>();
        body.add("file", new org.springframework.core.io.ByteArrayResource(fileContent) {
            @Override
            public String getFilename() {
                return fileName;
            }
        });
        return body;
    }
}