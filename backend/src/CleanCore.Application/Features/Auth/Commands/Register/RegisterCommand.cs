using CleanCore.Domain.Common;
using MediatR;

namespace CleanCore.Application.Features.Auth.Commands.Register;

public sealed record RegisterCommand(
    string Email,
    string Password,
    string FirstName,
    string LastName) : IRequest<Result<Guid>>;
