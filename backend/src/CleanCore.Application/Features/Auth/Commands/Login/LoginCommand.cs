using CleanCore.Domain.Common;
using MediatR;

namespace CleanCore.Application.Features.Auth.Commands.Login;

public sealed record LoginCommand(string Email, string Password) : IRequest<Result<AuthResponse>>;
